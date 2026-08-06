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
from datetime import date
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


@dataclass(frozen=True)
class YearPeak:
    """한 해의 최빈 주차. 연도별로 나눠야 반복 여부를 볼 수 있다."""

    iso_year: int
    iso_week: int
    count: int
    total: int

    @property
    def share(self) -> float:
        return round(self.count / self.total, 3) if self.total else 0.0


def peaks_by_year(upload_dates: list[str], min_per_year: int = 3) -> list[YearPeak]:
    """업로드 날짜 → 연도별 최빈 ISO 주차.

    월 단위 집계는 "4월 어디쯤"까지만 말한다. 주차로 쪼개고 연도별로 나눠야
    "작년에도 같은 주였나"를 물을 수 있다 — 반복 예측의 재료다.
    표본이 얇은 해는 한 편이 그 해를 대표해버리므로 버린다.
    """
    by_year: dict[int, list[int]] = {}
    for raw in upload_dates:
        try:
            day = date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
        except ValueError:
            continue
        iso = day.isocalendar()
        by_year.setdefault(iso[0], []).append(iso[1])

    peaks: list[YearPeak] = []
    for year, weeks in by_year.items():
        if len(weeks) < min_per_year:
            continue
        week, count = Counter(weeks).most_common(1)[0]
        peaks.append(YearPeak(iso_year=year, iso_week=week, count=count, total=len(weeks)))
    return sorted(peaks, key=lambda p: p.iso_year)


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
