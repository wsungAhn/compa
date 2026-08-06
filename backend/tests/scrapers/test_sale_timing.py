"""세일 시기 관측 — 하울 업로드 분포로 캘린더의 추측 날짜를 대체한다."""
import json

from app.core import sale_calendar
from app.scrapers.sale_timing import estimate, parse_upload_dates, to_record


def test_parses_yt_dlp_jsonl_and_ignores_noise() -> None:
    raw = '\n'.join([
        '[debug] not json',
        json.dumps({"upload_date": "20260415", "title": "haul"}),
        json.dumps({"title": "no date"}),
        json.dumps({"upload_date": "bad"}),
        json.dumps({"upload_date": "20250412"}),
    ])
    assert parse_upload_dates(raw) == ["20260415", "20250412"]


def test_estimate_finds_the_peak_month() -> None:
    dates = ["20260401", "20260415", "20250409", "20261102"]
    est = estimate("sephora sale haul", dates)
    assert est is not None
    assert est.peak_month == 4
    assert est.share == 0.75
    assert est.year_span == (2025, 2026)


def test_small_or_scattered_samples_are_not_confident() -> None:
    """프라임데이는 해마다 움직여 37%로 흩어졌다 — 그런 건 캘린더에 쓰지 않는다."""
    scattered = [f"2026{m:02d}01" for m in range(1, 13)] * 2
    est = estimate("amazon prime day beauty haul", scattered)
    assert est is not None and not est.is_confident

    tiny = estimate("q", ["20260401"] * 5)
    assert tiny is not None and not tiny.is_confident


def test_estimate_without_samples_is_none() -> None:
    assert estimate("q", []) is None


def test_measured_sales_drops_month_collisions(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """실측: "sephora fall sale haul"이 봄 하울까지 긁어와 4월로 나왔다.
    두 행사가 같은 달이면 하나는 쿼리가 잘못된 것이므로 뒤엣것을 버린다."""
    path = tmp_path / "sale_timing.json"
    path.write_text(json.dumps([
        {"event": "Sephora Savings Event (봄)", "peak_month": 4, "share": 0.9,
         "sample_size": 30, "confident": True},
        {"event": "Sephora Savings Event (가을)", "peak_month": 4, "share": 0.77,
         "sample_size": 30, "confident": True},
        {"event": "Ulta 21 Days of Beauty", "peak_month": 3, "share": 0.77,
         "sample_size": 30, "confident": True},
        {"event": "Amazon Prime Day", "peak_month": 7, "share": 0.37,
         "sample_size": 30, "confident": False},
    ]), encoding="utf-8")
    monkeypatch.setattr(sale_calendar, "_MEASURED_PATH", path)

    names = [s.name for s in sale_calendar.measured_sales()]
    assert "Sephora Savings Event (봄)" in names
    assert "Sephora Savings Event (가을)" not in names   # 월 충돌 → 버림
    assert "Amazon Prime Day" not in names              # 신뢰도 미달 → 버림
    assert "Ulta 21 Days of Beauty" in names


def test_missing_or_broken_file_is_not_fatal(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(sale_calendar, "_MEASURED_PATH", tmp_path / "nope.json")
    assert sale_calendar.measured_sales() == []

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(sale_calendar, "_MEASURED_PATH", broken)
    assert sale_calendar.measured_sales() == []


def test_guessed_dates_were_removed_from_rules() -> None:
    """적대감사 R1: 해마다 움직이는 행사를 고정일로 근사하면 틀린 D-day를 말한다."""
    rule_names = {name for name, _rule, _country in sale_calendar.RULES}
    assert not any("Sephora" in n for n in rule_names)
    assert "Amazon Prime Day" not in rule_names


def test_roundtrip_record_shape() -> None:
    est = estimate("q", ["20260401", "20260402"])
    assert est is not None
    rec = to_record(est)
    assert rec["peak_month"] == 4 and rec["months"] == {"4": 2}
