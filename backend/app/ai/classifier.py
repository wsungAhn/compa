"""정기/돌발 행사 분류 (Claude API)."""
from datetime import date

import anthropic
from pydantic import BaseModel

from app.core.config import settings

_KNOWN_REGULAR_EVENTS = {
    "black friday": 11,
    "블랙프라이데이": 11,
    "618": 6,
    "6.18": 6,
    "双11": 11,
    "쌍11": 11,
    "올영세일": None,
    "솔드아웃위크": None,
    "정기세일": None,
    "cyber monday": 11,
    "사이버먼데이": 11,
    "amazon prime day": 7,
    "프라임데이": 7,
}

_SURPRISE_KEYWORDS = ["재고소진", "신제품", "앱전용", "단독", "flash sale", "타임딜", "한정수량", "clearance"]


class ClassificationResult(BaseModel):
    event_type: str  # "regular" | "surprise"
    confidence: float
    reasoning: str


def classify_rule_based(event_name: str | None, reason: str | None, start_date: date | None) -> ClassificationResult | None:
    """규칙 기반 빠른 분류 — 명확한 경우 Claude 호출 생략."""
    name_lower = (event_name or "").lower()

    for known, month in _KNOWN_REGULAR_EVENTS.items():
        if known in name_lower:
            if month and start_date and start_date.month == month:
                return ClassificationResult(event_type="regular", confidence=0.97, reasoning=f"알려진 정기행사: {known}")
            elif not month:
                return ClassificationResult(event_type="regular", confidence=0.90, reasoning=f"알려진 정기행사: {known}")

    reason_lower = (reason or "").lower()
    for kw in _SURPRISE_KEYWORDS:
        if kw in reason_lower or kw in name_lower:
            return ClassificationResult(event_type="surprise", confidence=0.88, reasoning=f"돌발 키워드 감지: {kw}")

    return None  # 불명확 → Claude에게 위임


class EventClassifier:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def classify(
        self,
        event_name: str | None,
        reason: str | None,
        start_date: date | None,
        past_events: list[dict[str, object]],
    ) -> ClassificationResult:
        """정기/돌발 분류. 규칙으로 안 되면 Claude 사용."""
        rule_result = classify_rule_based(event_name, reason, start_date)
        if rule_result:
            return rule_result

        # Claude 호출
        history_text = "\n".join(
            f"- {e.get('event_name')} ({e.get('start_date')}, {e.get('event_type')})"
            for e in past_events[-10:]
        ) or "없음"

        prompt = f"""Classify this cosmetics sale event as "regular" or "surprise".

Event: {event_name or 'Unknown'}
Reason: {reason or 'Unknown'}
Date: {start_date or 'Unknown'}

Past events for same product:
{history_text}

Regular = recurring annually (same name/month appears in history, or well-known calendar events)
Surprise = one-time, stock clearance, new product launch, app-exclusive, brand anniversary

Respond with JSON only:
{{"event_type": "regular" or "surprise", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}"""

        import json

        response = self._client.messages.create(
            model=settings.anthropic_model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            data = json.loads(response.content[0].text.strip())
            return ClassificationResult(**data)
        except Exception:
            return ClassificationResult(event_type="surprise", confidence=0.5, reasoning="분류 실패, 기본값 적용")
