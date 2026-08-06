"""세일 시기 관측 — 하울 업로드 분포로 캘린더의 추측 날짜를 대체한다."""
import json
from datetime import date

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


def test_month_collisions_are_merged_not_discarded(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """실측: "sephora fall sale haul"이 봄 하울까지 긁어와 4월로 나왔다.
    라벨은 틀렸지만 **4월이라는 관측 자체는 공짜로 얻은 두 번째 증거**다 — 버리지 않고
    표본을 합산한다."""
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

    sales = {s.month: s for s in sale_calendar.measured_sales()}
    april = sales[4]
    assert april.sample_size == 60          # 30 + 30, 두 쿼리 합산
    assert april.corroborations == 2        # 독립 쿼리 2개가 4월을 지지
    assert 0.77 <= april.share <= 0.90      # 가중 평균
    assert sales[3].corroborations == 1     # Ulta는 단독 관측
    assert 7 not in sales                   # 프라임데이는 신뢰도 미달 → 제외


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


def test_peaks_by_year_splits_weeks_per_year() -> None:
    """월 집계는 "4월 어디쯤"까지다 — 반복을 보려면 연도별 주차로 쪼개야 한다."""
    from app.scrapers.sale_timing import peaks_by_year

    dates = ["20221125", "20221126", "20221128", "20211126", "20211127", "20211129"]
    peaks = {p.iso_year: p.iso_week for p in peaks_by_year(dates)}
    assert peaks == {2021: 47, 2022: 47}


def test_thin_years_are_dropped() -> None:
    """한 편이 그 해를 대표해버리면 안 된다."""
    from app.scrapers.sale_timing import peaks_by_year

    assert peaks_by_year(["20220401", "20230401"]) == []


def test_predictions_do_not_override_exact_rules(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """블프는 "11월 넷째 목요일 다음날"로 확정된다. 하울 분포는 W47/W48에 걸쳐
    median이 한 주 어긋나므로, 규칙이 있으면 규칙이 이긴다."""
    import json as _json

    path = tmp_path / "sale_timing.json"
    path.write_text(_json.dumps({
        "months": [],
        "predictions": [
            {"recurrence_key": "black_friday", "iso_week": 47, "years_observed": 11,
             "week_spread": 20, "concentration": 0.91, "label": "Black Friday", "reliable": True},
            {"recurrence_key": "some_new_event", "iso_week": 20, "years_observed": 4,
             "week_spread": 1, "concentration": 0.9, "label": "New Event", "reliable": True},
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(sale_calendar, "_MEASURED_PATH", path)

    names = [s.name for s in sale_calendar.predicted_sales(date(2026, 1, 5))]
    assert "Black Friday" not in names   # 규칙이 담당
    assert "New Event" in names          # 규칙이 없는 자리는 예측이 메운다
