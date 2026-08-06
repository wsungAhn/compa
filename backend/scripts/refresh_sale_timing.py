#!/usr/bin/env python3
"""세일 시기 관측치 갱신 — 하울 영상 업로드 날짜 분포를 세어 JSON으로 남긴다.

수동/저빈도 실행이다(월 1회면 충분하다 — 세일 일정은 해마다 한 번 움직인다).
요청 경로에서 부르지 않는다: yt-dlp 검색은 쿼리당 수십 초가 걸린다.

    python scripts/refresh_sale_timing.py            # 전체 갱신
    python scripts/refresh_sale_timing.py --limit 20 # 표본 축소(빠른 확인)
"""
import argparse
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import asyncio  # noqa: E402

from app.core import sale_windows  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.scrapers.sale_timing import (  # noqa: E402
    estimate,
    parse_upload_dates,
    peaks_by_year,
    to_record,
)

YTDLP = pathlib.Path.home() / "dev/firecrawl-local/.venv/bin/yt-dlp"
OUT = pathlib.Path(__file__).resolve().parents[1] / "app" / "data" / "sale_timing.json"

# (캘린더 이벤트 이름, 검색 쿼리) — 이름은 sale_calendar의 RULES와 맞춘다.
# (캘린더 이벤트 이름, 검색 쿼리, 연도 간 조인 키)
TARGETS: list[tuple[str, str, str]] = [
    ("Sephora Savings Event (봄)", "sephora sale haul", "sephora_spring"),
    ("Sephora Savings Event (가을)", "sephora fall sale haul", "sephora_fall"),
    ("Ulta 21 Days of Beauty", "ulta 21 days of beauty haul", "ulta_21days"),
    ("Black Friday", "black friday beauty haul", "black_friday"),
    ("Amazon Prime Day", "amazon prime day beauty haul", "amazon_prime_day"),
]


async def _write_and_predict(
    jobs: list[tuple[str, str, str, list[str]]],
) -> tuple[dict[str, int], list[dict[str, object]]]:
    """연도별 최빈 주차를 sale_windows에 추정(is_estimate)으로 남긴다.

    세션을 한 번만 연다 — asyncio.run을 여러 번 호출하면 asyncpg 커넥션이 이전
    이벤트 루프에 묶여 터진다.
    """
    written: dict[str, int] = {}
    async with AsyncSessionLocal() as db:
        for name, key, retailer, dates in jobs:
          for peak in peaks_by_year(dates):
            row = await sale_windows.record(
                db,
                sale_windows.Observation(
                    brand=retailer,
                    source="youtube_timing",
                    on=sale_windows.monday_of(peak.iso_year, peak.iso_week),
                    event_name=name,
                    retailer=retailer,
                    country="US",
                    is_estimate=True,
                    sample_size=peak.total,
                    confidence=peak.share,
                    recurrence_key=key,
                    source_url=f"ytsearch:{key}:{peak.iso_year}",
                ),
            )
            if row is not None:
                written[key] = written.get(key, 0) + 1
        await db.commit()

        # 요청 경로는 DB를 뒤지지 않는다 — 여기서 컴파일해 JSON으로 넘긴다.
        preds: list[dict[str, object]] = []
        for _name, key, _retailer, _dates in jobs:
            pred = await sale_windows.predict(db, key)
            if not pred:
                continue
            preds.append({
                "recurrence_key": pred.recurrence_key,
                "iso_week": pred.iso_week,
                "years_observed": pred.years_observed,
                "week_spread": pred.week_spread,
                "concentration": pred.concentration,
                "label": pred.label,
                "reliable": pred.is_reliable,
            })
    return written, preds


def search_upload_dates(query: str, limit: int) -> list[str]:
    proc = subprocess.run(
        [str(YTDLP), f"ytsearch{limit}:{query}", "--dump-json", "--no-warnings", "--skip-download"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    return parse_upload_dates(proc.stdout)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=40, help="쿼리당 검색 표본 수")
    args = parser.parse_args()

    records: list[dict[str, object]] = []
    jobs: list[tuple[str, str, str, list[str]]] = []
    for name, query, key in TARGETS:
        dates = search_upload_dates(query, args.limit)
        est = estimate(query, dates)
        if not est:
            print(f"  {name:32} 표본 없음")
            continue
        record = to_record(est)
        record["event"] = name
        record["recurrence_key"] = key
        records.append(record)
        jobs.append((name, key, name.split(" ")[0], dates))
        flag = "✅" if est.is_confident else "⚠️ 신뢰도 낮음"
        span = f"{est.year_span[0]}~{est.year_span[1]}" if est.year_span else "?"
        print(f"  {name:32} {est.peak_month:2}월 {est.share:.0%} (n={est.sample_size}, {span}) {flag}")

    slots, predictions = asyncio.run(_write_and_predict(jobs))
    if slots:
        print("\n  슬롯 적재(연도 수):", ", ".join(f"{k} {v}" for k, v in slots.items()))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"months": records, "predictions": predictions}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ok = [p for p in predictions if p["reliable"]]
    print(f"  예측 {len(predictions)}건 중 신뢰 가능 {len(ok)}건: " +
          ", ".join(f"{p['recurrence_key']} W{p['iso_week']}" for p in ok))
    print(f"\n저장: {OUT}")


if __name__ == "__main__":
    main()
