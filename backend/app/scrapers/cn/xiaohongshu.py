import json
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.core.proxy import httpx_proxy
from app.scrapers.base import BaseScraper, ScrapedEvent

_SEARCH_URL = "https://www.xiaohongshu.com/search_result?keyword={query}"


def _find_notes(obj: object) -> list[dict[str, Any]]:
    """Recursively find note objects containing title-ish and id keys.

    Args:
        obj: Object to search (typically a dict or list from parsed JSON)

    Returns:
        List of note dictionaries found
    """
    notes: list[dict[str, Any]] = []

    if isinstance(obj, dict):
        # Check if this dict looks like a note
        has_title = any(k in obj for k in ("title", "displayTitle", "noteTitle", "note_title"))
        has_id = "id" in obj

        if has_title and has_id:
            notes.append(obj)

        # Recursively search nested structures
        for value in obj.values():
            notes.extend(_find_notes(value))

    elif isinstance(obj, list):
        for item in obj:
            notes.extend(_find_notes(item))

    return notes


def parse_initial_state(html: str, url: str) -> list[ScrapedEvent]:
    """Parse Xiaohongshu HTML extracting initial state JSON and notes.

    Args:
        html: HTML content from search page
        url: Source URL for the search

    Returns:
        List of ScrapedEvent objects extracted from the HTML
    """
    events: list[ScrapedEvent] = []
    soup = BeautifulSoup(html, "html.parser")

    # Find script tag with __INITIAL_STATE__
    script_tag = None
    for script in soup.find_all("script"):
        if script.string and "__INITIAL_STATE__" in script.string:
            script_tag = script
            break

    if not script_tag or not script_tag.string:
        return events

    script_content = script_tag.string

    # Extract JSON: find "window.__INITIAL_STATE__=" and extract until </script>
    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(.+?)(?:</script>|$)", script_content, re.DOTALL)
    if not match:
        return events

    json_str = match.group(1).strip()

    # Handle trailing semicolon
    if json_str.endswith(";"):
        json_str = json_str[:-1]

    # Handle undefined values: replace with null for JSON parsing
    json_str = json_str.replace("undefined", "null")

    try:
        state = json.loads(json_str)
    except json.JSONDecodeError:
        return events

    # Find notes in the state object
    notes = _find_notes(state)

    # Extract events from notes, max 5
    for note in notes[:5]:
        try:
            # Get title (use first available key)
            title = ""
            for key in ("title", "displayTitle", "noteTitle", "note_title"):
                if key in note:
                    title = str(note[key])
                    break

            if not title:
                continue

            # Get note ID
            note_id = note.get("id", "")

            # Get description if available
            desc = note.get("desc", "") or note.get("description", "") or ""
            if isinstance(desc, dict):
                desc = str(desc)
            else:
                desc = str(desc) if desc else ""

            # Build raw_text from title and description
            raw_text = f"{title} {desc}"[:500].strip()

            # Build source URL with note ID
            source_url = url
            if note_id:
                source_url = f"https://www.xiaohongshu.com/explore/{note_id}"

            # Truncate title to 100 chars for event_name
            event_name = title[:100]

            events.append(
                ScrapedEvent(
                    product_name=state.get("search", {}).get("keyword", "") if isinstance(state.get("search"), dict) else "",
                    event_name=event_name,
                    reason=None,
                    currency="CNY",
                    source_url=source_url,
                    confidence=0.5,
                    raw_text=raw_text,
                )
            )
        except Exception:
            continue

    return events


class XiaohongshuScraper(BaseScraper):
    PLATFORM_NAME = "小红书"
    COUNTRY = "CN"
    RATE_LIMIT_SEC = 2.0

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        try:
            await self._wait_rate_limit()

            url = _SEARCH_URL.format(query=query)
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9",
            }

            proxy = httpx_proxy()

            async with httpx.AsyncClient(
                timeout=30.0, follow_redirects=True, proxy=proxy
            ) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                html = response.text

            events = parse_initial_state(html, url)

        except Exception as exc:
            events.append(
                ScrapedEvent(
                    product_name=query,
                    confidence=0.0,
                    raw_text=str(exc),
                )
            )

        return events
