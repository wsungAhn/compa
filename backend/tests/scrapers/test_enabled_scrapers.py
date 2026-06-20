from unittest.mock import MagicMock

from app.scrapers import collector


def test_get_enabled_scrapers_default_safe_subset(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(collector, "settings", MagicMock(enabled_scrapers="네이버쇼핑,Rakuten"))

    enabled = collector.get_enabled_scrapers()

    assert list(enabled.keys()) == ["네이버쇼핑", "Rakuten"]


def test_get_enabled_scrapers_all(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(collector, "settings", MagicMock(enabled_scrapers="all"))

    enabled = collector.get_enabled_scrapers()

    assert enabled.keys() == collector.SCRAPERS.keys()


def test_get_enabled_scrapers_ignores_unknown_names(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(collector, "settings", MagicMock(enabled_scrapers="네이버쇼핑,Nope,Rakuten"))

    enabled = collector.get_enabled_scrapers()

    assert list(enabled.keys()) == ["네이버쇼핑", "Rakuten"]


def test_collect_fast_candidates_respect_enabled(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(collector, "settings", MagicMock(enabled_scrapers="Rakuten"))

    enabled_fast = [name for name in collector.FAST_SCRAPERS if name in collector.get_enabled_scrapers()]

    assert enabled_fast == []
