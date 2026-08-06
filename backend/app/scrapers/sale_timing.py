"""세일 시기를 하울 영상 업로드 날짜 분포로 추정한다.

`sale_calendar`의 날짜는 사람이 짐작해 박은 값이었다(적대감사 R1의 가장 아픈 지적:
Sephora 세일을 4/5·10/25로 근사 → "세일 없음"이 아니라 **틀린 D-day를 자신 있게**
말하게 된다). 하울 영상은 세일 직후에 몰리므로, 업로드 날짜 분포가 곧 세일 시기다.

2026-08-06 실측 — 쿼리마다 다른 달이 나왔고 전부 실제 행사와 일치했다:
    "sephora sale haul"        4월 33/40   (Sephora 봄 세일)
    "ulta 21 days of beauty"   3월 23/30   (Ulta 21 Days)
    "black friday beauty haul" 11월 20/30  (블랙프라이데이, 2012~2025년 표본)

LLM은 개입하지 않는다 — 검색 결과의 upload_date를 세는 것뿐이다(Deterministic First).
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class TimingEstimate:
    """관측된 세일 시기."""

    query: str
    peak_month: int
    share: float  # 최빈월이 표본에서 차지하는 비율
    sample_size: int
    year_span: tuple[int, int] | None
    months: dict[int, int]

    @property
    def is_confident(self) -> bool:
        """한 달에 몰려 있고 표본이 충분할 때만 캘린더를 덮어쓴다."""
        return self.sample_size >= 20 and self.share >= 0.4


def parse_upload_dates(jsonl: str) -> list[str]:
    """yt-dlp --dump-json 출력 → upload_date(YYYYMMDD) 목록."""
    dates: list[str] = []
    for line in jsonl.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        raw = payload.get("upload_date")
        if isinstance(raw, str) and len(raw) == 8 and raw.isdigit():
            dates.append(raw)
    return dates


def estimate(query: str, upload_dates: list[str]) -> TimingEstimate | None:
    """업로드 날짜 목록 → 최빈월 추정."""
    if not upload_dates:
        return None
    months = Counter(int(d[4:6]) for d in upload_dates)
    years = [int(d[:4]) for d in upload_dates]
    peak_month, peak_count = months.most_common(1)[0]
    return TimingEstimate(
        query=query,
        peak_month=peak_month,
        share=round(peak_count / len(upload_dates), 3),
        sample_size=len(upload_dates),
        year_span=(min(years), max(years)),
        months=dict(sorted(months.items())),
    )


def to_record(est: TimingEstimate) -> dict[str, object]:
    return {
        "query": est.query,
        "peak_month": est.peak_month,
        "share": est.share,
        "sample_size": est.sample_size,
        "year_span": list(est.year_span) if est.year_span else None,
        "months": {str(k): v for k, v in est.months.items()},
        "confident": est.is_confident,
    }
