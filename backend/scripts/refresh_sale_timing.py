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

from app.scrapers.sale_timing import estimate, parse_upload_dates, to_record  # noqa: E402

YTDLP = pathlib.Path.home() / "dev/firecrawl-local/.venv/bin/yt-dlp"
OUT = pathlib.Path(__file__).resolve().parents[1] / "app" / "data" / "sale_timing.json"

# (캘린더 이벤트 이름, 검색 쿼리) — 이름은 sale_calendar의 RULES와 맞춘다.
TARGETS: list[tuple[str, str]] = [
    ("Sephora Savings Event (봄)", "sephora sale haul"),
    ("Sephora Savings Event (가을)", "sephora fall sale haul"),
    ("Ulta 21 Days of Beauty", "ulta 21 days of beauty haul"),
    ("Black Friday", "black friday beauty haul"),
    ("Amazon Prime Day", "amazon prime day beauty haul"),
]


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
    for name, query in TARGETS:
        dates = search_upload_dates(query, args.limit)
        est = estimate(query, dates)
        if not est:
            print(f"  {name:32} 표본 없음")
            continue
        record = to_record(est)
        record["event"] = name
        records.append(record)
        flag = "✅" if est.is_confident else "⚠️ 신뢰도 낮음"
        span = f"{est.year_span[0]}~{est.year_span[1]}" if est.year_span else "?"
        print(f"  {name:32} {est.peak_month:2}월 {est.share:.0%} (n={est.sample_size}, {span}) {flag}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n저장: {OUT}")


if __name__ == "__main__":
    main()
