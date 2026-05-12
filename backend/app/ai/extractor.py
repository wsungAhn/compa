"""소셜 비정형 텍스트 → 구조화 데이터 추출 (Claude API, 프리미엄 전용)."""
from datetime import date

import anthropic
from pydantic import BaseModel

from app.core.config import settings

# 시스템 프롬프트 — 1024토큰 이상이므로 캐싱 적용
_SYSTEM_PROMPT = """\
You are a cosmetics discount event extractor. Extract structured sale information from social media posts and shopping mall texts written in Korean, English, Japanese, or Chinese.

Output a JSON array where each element follows this schema:
{
  "product_name": "string (required)",
  "brand": "string or null",
  "original_price": "number or null",
  "sale_price": "number or null",
  "discount_rate": "number or null (percentage, e.g. 30 means 30%)",
  "currency": "KRW | USD | JPY | CNY | null",
  "start_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null",
  "event_name": "string or null (e.g. 블랙프라이데이, 618, 올영세일)",
  "reason": "string or null (why is it on sale? e.g. 재고소진, 신제품출시, 기념일)",
  "confidence": "float 0.0-1.0 (how confident are you in the extraction)"
}

Confidence scoring rules:
- 1.0: All key fields present, clear and unambiguous
- 0.8-0.9: Most fields present, minor ambiguity
- 0.5-0.7: Partial information, some fields inferred
- Below 0.5: Very little concrete information

Few-shot examples:

Input: "[올영세일] 설화수 윤조에센스 30% 할인! 6/1~6/7까지"
Output: [{"product_name":"설화수 윤조에센스","brand":"설화수","discount_rate":30,"currency":"KRW","start_date":"2024-06-01","end_date":"2024-06-07","event_name":"올영세일","reason":null,"original_price":null,"sale_price":null,"confidence":0.95}]

Input: "Sephora Black Friday sale! Sulwhasoo First Care Activating Serum $85 (was $120)"
Output: [{"product_name":"Sulwhasoo First Care Activating Serum","brand":"Sulwhasoo","original_price":120,"sale_price":85,"discount_rate":29.2,"currency":"USD","event_name":"Black Friday","reason":null,"start_date":null,"end_date":null,"confidence":0.98}]

Input: "SK-IIのフェイシャルトリートメントエッセンス、今だけ20%オフ！数量限定です"
Output: [{"product_name":"SK-II フェイシャルトリートメントエッセンス","brand":"SK-II","discount_rate":20,"currency":"JPY","event_name":null,"reason":"数量限定","start_date":null,"end_date":null,"original_price":null,"sale_price":null,"confidence":0.85}]

Input: "雅诗兰黛小棕瓶双十一预售价699，比去年便宜了50块"
Output: [{"product_name":"雅诗兰黛 小棕瓶精华","brand":"雅诗兰黛","sale_price":699,"currency":"CNY","event_name":"双11","reason":null,"start_date":null,"end_date":null,"discount_rate":null,"original_price":null,"confidence":0.82}]

Rules:
- Never invent data not present in the text
- If information is ambiguous, lower confidence score
- Never include PII (names, emails, phone numbers)
- Return empty array [] if no cosmetics discount information found
- Always return valid JSON array, no markdown code blocks
"""


class ExtractedEvent(BaseModel):
    product_name: str
    brand: str | None = None
    original_price: float | None = None
    sale_price: float | None = None
    discount_rate: float | None = None
    currency: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    event_name: str | None = None
    reason: str | None = None
    confidence: float = 0.5

    @property
    def needs_review(self) -> bool:
        return self.confidence < 0.7


class SocialExtractor:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def extract_batch(self, posts: list[str]) -> list[ExtractedEvent]:
        """소셜 포스트 최대 20개 배치 처리."""
        if not posts:
            return []

        batch = posts[:20]
        numbered = "\n\n".join(f"[{i+1}] {p}" for i, p in enumerate(batch))
        user_message = f"Extract all cosmetics discount events from these {len(batch)} posts:\n\n{numbered}"

        import json

        response = self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
        )

        raw = response.content[0].text.strip()

        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                data = [data]
        except json.JSONDecodeError:
            # JSON 블록 안에 있을 경우 추출
            import re
            m = re.search(r"\[.*\]", raw, re.DOTALL)
            data = json.loads(m.group()) if m else []

        results: list[ExtractedEvent] = []
        for item in data:
            try:
                # 날짜 문자열 → date 변환
                for field in ("start_date", "end_date"):
                    if isinstance(item.get(field), str):
                        try:
                            item[field] = date.fromisoformat(item[field])
                        except ValueError:
                            item[field] = None
                results.append(ExtractedEvent(**item))
            except Exception:
                continue

        return results
