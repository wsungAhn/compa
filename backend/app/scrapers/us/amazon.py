import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.proxy import httpx_proxy
from app.scrapers.base import BaseScraper, ScrapedEvent

_SEARCH_URL = "https://www.amazon.com/s?k={query}&i=beauty"
_PRICE_RE = re.compile(r"[\d,]+")
_PAAPI_HOST = "webservices.amazon.com"
_PAAPI_REGION = "us-east-1"
_PAAPI_SERVICE = "ProductAdvertisingAPI"
_PAAPI_PATH = "/paapi5/searchitems"
_PAAPI_TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"


def _sign_request_aws_v4(
    payload_json: str,
    access_key: str,
    secret_key: str,
    amz_date: str,
    date_stamp: str,
) -> dict[str, str]:
    """Generate AWS Signature V4 headers for PA-API request.

    Args:
        payload_json: JSON request body
        access_key: AWS access key ID
        secret_key: AWS secret access key
        amz_date: ISO 8601 datetime string (e.g., '20260101T000000Z')
        date_stamp: Date string (e.g., '20260101')

    Returns:
        Dictionary of HTTP headers including Authorization and X-Amz-Date.
    """
    # Canonical request components
    http_method = "POST"
    canonical_uri = _PAAPI_PATH
    canonical_querystring = ""

    # Headers for canonical request
    canonical_headers_dict: dict[str, str] = {
        "content-type": "application/json; charset=utf-8",
        "host": _PAAPI_HOST,
        "x-amz-date": amz_date,
        "x-amz-target": _PAAPI_TARGET,
    }
    canonical_headers_list = [
        f"{k}:{v}" for k, v in sorted(canonical_headers_dict.items())
    ]
    canonical_headers = "\n".join(canonical_headers_list) + "\n"

    signed_headers = ";".join(sorted(canonical_headers_dict.keys()))

    # Payload hash
    payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    # Canonical request
    canonical_request = (
        f"{http_method}\n"
        f"{canonical_uri}\n"
        f"{canonical_querystring}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )

    # String to sign
    credential_scope = f"{date_stamp}/{_PAAPI_REGION}/{_PAAPI_SERVICE}/aws4_request"
    canonical_request_hash = hashlib.sha256(
        canonical_request.encode("utf-8")
    ).hexdigest()
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n{canonical_request_hash}"
    )

    # Signing key chain
    k_date = hmac.new(
        f"AWS4{secret_key}".encode("utf-8"), date_stamp.encode("utf-8"), hashlib.sha256
    ).digest()
    k_region = hmac.new(
        k_date, _PAAPI_REGION.encode("utf-8"), hashlib.sha256
    ).digest()
    k_service = hmac.new(
        k_region, _PAAPI_SERVICE.encode("utf-8"), hashlib.sha256
    ).digest()
    k_signing = hmac.new(
        k_service, b"aws4_request", hashlib.sha256
    ).digest()

    signature = hmac.new(
        k_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    # Authorization header
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    return {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "X-Amz-Date": amz_date,
        "X-Amz-Target": _PAAPI_TARGET,
    }


def build_paapi_request(query: str, partner_tag: str) -> dict[str, Any]:
    """Build a ProductAdvertisingAPI SearchItems request payload.

    Args:
        query: Product search query
        partner_tag: Amazon Associates Partner Tag

    Returns:
        Dictionary ready for JSON serialization as PA-API request.
    """
    return {
        "Keywords": query,
        "SearchIndex": "Beauty",
        "ItemCount": 5,
        "PartnerTag": partner_tag,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.com",
        "Resources": [
            "ItemInfo.Title",
            "Offers.Listings.Price",
            "Offers.Listings.SavingBasis",
        ],
    }


def parse_paapi_response(data: dict[str, Any], url: str) -> list[ScrapedEvent]:
    """Parse ProductAdvertisingAPI response and extract product events.

    Args:
        data: Parsed JSON response from PA-API
        url: Source URL

    Returns:
        List of ScrapedEvent objects extracted from the response.
    """
    events: list[ScrapedEvent] = []

    try:
        items = data.get("SearchResult", {}).get("Items", [])
    except (AttributeError, TypeError):
        return events

    for item in items:
        try:
            # Title
            item_info = item.get("ItemInfo", {})
            title_obj = item_info.get("Title", {})
            product_name = title_obj.get("DisplayValue", "")
            if not product_name:
                continue

            # Price and saving basis
            offers = item.get("Offers", {})
            listings = offers.get("Listings", [])
            if not listings:
                continue

            listing = listings[0]
            price_obj = listing.get("Price", {})
            sale_price = price_obj.get("Amount")

            if sale_price is None:
                continue

            try:
                sale_price = float(sale_price)
            except (ValueError, TypeError):
                continue

            # Original price (from SavingBasis)
            saving_basis_obj = listing.get("SavingBasis", {})
            original_price = saving_basis_obj.get("Amount")

            if original_price is not None:
                try:
                    original_price = float(original_price)
                except (ValueError, TypeError):
                    original_price = None

            # Discount rate
            discount_rate: float | None = None
            if original_price and sale_price and original_price > 0:
                discount_rate = round((1 - sale_price / original_price) * 100, 1)

            # Source URL
            source_url = item.get("DetailPageURL", url)

            events.append(
                ScrapedEvent(
                    product_name=product_name,
                    original_price=original_price,
                    sale_price=sale_price,
                    discount_rate=discount_rate if discount_rate and discount_rate > 0 else None,
                    currency="USD",
                    event_name="Amazon 현재가",
                    source_url=source_url,
                    confidence=0.95,
                    raw_text=product_name,
                )
            )
        except Exception:
            continue

    return events


def _parse_price(whole: str, fraction: str = "00") -> float | None:
    w = whole.strip().replace(",", "")
    f = fraction.strip()
    if not w.isdigit():
        return None
    return float(f"{w}.{f}")


def parse_search_html(html: str, url: str) -> list[ScrapedEvent]:
    """Parse Amazon search HTML and extract product events.

    Args:
        html: HTML content from search page
        url: Source URL for the search

    Returns:
        List of ScrapedEvent objects extracted from the HTML
    """
    events: list[ScrapedEvent] = []
    soup = BeautifulSoup(html, "html.parser")
    results = soup.select('div[data-component-type="s-search-result"]')

    for item in results[:5]:
        try:
            name_el = item.select_one("h2 a span")
            name = name_el.get_text(strip=True) if name_el else ""

            whole_el = item.select_one("span.a-price-whole")
            frac_el = item.select_one("span.a-price-fraction")
            if not whole_el:
                continue
            sale_price = _parse_price(
                whole_el.get_text(strip=True).rstrip("."),
                frac_el.get_text(strip=True) if frac_el else "00",
            )
            if not sale_price:
                continue

            orig_el = item.select_one("span.a-text-price span.a-offscreen")
            original_price: float | None = None
            if orig_el:
                m = _PRICE_RE.search(orig_el.get_text(strip=True).replace(",", ""))
                original_price = float(m.group()) if m else None

            discount_rate: float | None = None
            if original_price and sale_price and original_price > 0:
                discount_rate = round((1 - sale_price / original_price) * 100, 1)

            link_el = item.select_one("h2 a")
            href_attr = link_el.get("href", "") if link_el else ""
            href = href_attr if isinstance(href_attr, str) else ""
            source_url = f"https://www.amazon.com{href}" if href.startswith("/") else url

            events.append(
                ScrapedEvent(
                    product_name=name,
                    original_price=original_price,
                    sale_price=sale_price,
                    discount_rate=discount_rate if discount_rate and discount_rate > 0 else None,
                    currency="USD",
                    event_name="Amazon 현재가",
                    source_url=source_url,
                    confidence=0.8,
                    raw_text=item.get_text(strip=True)[:300],
                )
            )
        except Exception:
            continue

    return events


class AmazonScraper(BaseScraper):
    PLATFORM_NAME = "Amazon US"
    COUNTRY = "US"
    RATE_LIMIT_SEC = 2.0

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        use_paapi = (
            settings.amazon_access_key
            and settings.amazon_secret_key
            and settings.amazon_partner_tag
        )

        if use_paapi:
            events = await self._scrape_paapi(query)
            if events:
                return events

        # Fallback to HTML scraping
        return await self._scrape_html(query)

    async def _scrape_paapi(self, query: str) -> list[ScrapedEvent]:
        """Scrape using ProductAdvertisingAPI with AWS Signature V4.

        Args:
            query: Product search query

        Returns:
            List of ScrapedEvent objects, or empty list on any error.
        """
        events: list[ScrapedEvent] = []
        try:
            await self._wait_rate_limit()

            # Get current timestamp
            now = datetime.now(timezone.utc)
            amz_date = now.strftime("%Y%m%dT%H%M%SZ")
            date_stamp = now.strftime("%Y%m%d")

            # Build payload
            payload = build_paapi_request(query, settings.amazon_partner_tag)
            payload_json = json.dumps(payload, separators=(",", ":"))

            # Sign request
            headers = _sign_request_aws_v4(
                payload_json,
                settings.amazon_access_key,
                settings.amazon_secret_key,
                amz_date,
                date_stamp,
            )

            # Make request
            url = f"https://{_PAAPI_HOST}{_PAAPI_PATH}"
            proxy = httpx_proxy()

            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True, proxy=proxy
            ) as client:
                resp = await client.post(url, headers=headers, content=payload_json)
                resp.raise_for_status()
                data = resp.json()

            events = parse_paapi_response(data, url)

        except Exception:
            # Any PA-API error triggers fallback
            pass

        return events

    async def _scrape_html(self, query: str) -> list[ScrapedEvent]:
        """Scrape using HTML parsing fallback.

        Args:
            query: Product search query

        Returns:
            List of ScrapedEvent objects.
        """
        events: list[ScrapedEvent] = []
        try:
            await self._wait_rate_limit()
            url = _SEARCH_URL.format(query=query.replace(" ", "+"))
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            proxy = httpx_proxy()

            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True, proxy=proxy
            ) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                html = resp.text

            events = parse_search_html(html, url)

        except Exception as exc:
            events.append(
                ScrapedEvent(
                    product_name=query,
                    confidence=0.0,
                    raw_text=str(exc),
                )
            )
        return events
