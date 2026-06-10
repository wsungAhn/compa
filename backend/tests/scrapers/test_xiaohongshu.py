"""小红书 (Xiaohongshu) 스크래퍼 단위 테스트 (실제 HTTP 호출 없음)."""
import json

from app.scrapers.cn.xiaohongshu import XiaohongshuScraper, _find_notes, parse_initial_state


def test_find_notes_empty() -> None:
    result = _find_notes({})
    assert result == []


def test_find_notes_single_note() -> None:
    obj = {
        "id": "abc123",
        "title": "Test Note",
        "desc": "Test description"
    }
    result = _find_notes(obj)
    assert len(result) == 1
    assert result[0]["id"] == "abc123"
    assert result[0]["title"] == "Test Note"


def test_find_notes_nested_in_dict() -> None:
    obj = {
        "search": {
            "notes": [
                {
                    "id": "note1",
                    "title": "Note 1",
                    "desc": "Desc 1"
                },
                {
                    "id": "note2",
                    "displayTitle": "Note 2",
                    "description": "Desc 2"
                }
            ]
        }
    }
    result = _find_notes(obj)
    assert len(result) == 2


def test_find_notes_missing_title() -> None:
    """Notes without title-like keys should be skipped."""
    obj = {
        "id": "abc123",
        "content": "Just some content",
    }
    result = _find_notes(obj)
    assert len(result) == 0


def test_find_notes_missing_id() -> None:
    """Notes without id should be skipped."""
    obj = {
        "title": "Some Title",
        "desc": "Some description",
    }
    result = _find_notes(obj)
    assert len(result) == 0


def test_scraper_platform_attrs() -> None:
    scraper = XiaohongshuScraper()
    assert scraper.PLATFORM_NAME == "小红书"
    assert scraper.COUNTRY == "CN"
    assert scraper.RATE_LIMIT_SEC == 2.0


def test_parse_initial_state_empty_html() -> None:
    html = ""
    events = parse_initial_state(html, "http://example.com")
    assert events == []


def test_parse_initial_state_no_marker() -> None:
    """HTML without __INITIAL_STATE__ marker should return empty."""
    html = "<html><body>No state here</body></html>"
    events = parse_initial_state(html, "http://example.com")
    assert events == []


def test_parse_initial_state_with_one_note() -> None:
    """Test parsing HTML with window.__INITIAL_STATE__ containing a single note."""
    state_data = {
        "search": {
            "keyword": "雅诗兰黛",
            "notes": [
                {
                    "id": "abc123",
                    "title": "雅诗兰黛小棕瓶 618特价",
                    "desc": "便宜50块"
                }
            ]
        }
    }
    state_json = json.dumps(state_data)
    html = f"""
    <html>
    <script>
    window.__INITIAL_STATE__ = {state_json}</script>
    </html>
    """
    url = "https://www.xiaohongshu.com/search_result?keyword=雅诗兰黛"
    events = parse_initial_state(html, url)

    assert len(events) == 1
    event = events[0]
    assert event.event_name == "雅诗兰黛小棕瓶 618特价"
    assert event.source_url == "https://www.xiaohongshu.com/explore/abc123"
    assert event.confidence == 0.5
    assert "雅诗兰黛小棕瓶 618特价" in event.raw_text
    assert "便宜50块" in event.raw_text
    assert event.currency == "CNY"


def test_parse_initial_state_with_multiple_notes() -> None:
    """Test parsing with multiple notes, should limit to 5."""
    notes = []
    for i in range(10):
        notes.append({
            "id": f"note_{i}",
            "title": f"Note {i}",
            "desc": f"Description {i}"
        })

    state_data = {
        "search": {
            "keyword": "test",
            "notes": notes
        }
    }
    state_json = json.dumps(state_data)
    html = f'<script>window.__INITIAL_STATE__ = {state_json}</script>'
    url = "https://www.xiaohongshu.com/search_result?keyword=test"
    events = parse_initial_state(html, url)

    assert len(events) == 5
    for i in range(5):
        assert events[i].event_name == f"Note {i}"


def test_parse_initial_state_undefined_handling() -> None:
    """Test that undefined values are converted to null for JSON parsing."""
    html = """
    <script>
    window.__INITIAL_STATE__ = {"search": {"keyword": "test", "notes": [{"id": "123", "title": "Test", "desc": undefined}]}}
    </script>
    """
    url = "https://www.xiaohongshu.com/search_result?keyword=test"
    events = parse_initial_state(html, url)

    assert len(events) == 1
    assert events[0].event_name == "Test"


def test_parse_initial_state_alt_title_keys() -> None:
    """Test different title-like keys: displayTitle, noteTitle."""
    state_data = {
        "notes": [
            {
                "id": "a",
                "displayTitle": "Note with displayTitle",
                "desc": "Desc A"
            },
            {
                "id": "b",
                "noteTitle": "Note with noteTitle",
                "desc": "Desc B"
            }
        ]
    }
    state_json = json.dumps(state_data)
    html = f'<script>window.__INITIAL_STATE__ = {state_json}</script>'
    url = "https://www.xiaohongshu.com/search"
    events = parse_initial_state(html, url)

    assert len(events) == 2
    assert events[0].event_name == "Note with displayTitle"
    assert events[1].event_name == "Note with noteTitle"


def test_parse_initial_state_no_notes() -> None:
    """Valid __INITIAL_STATE__ but no notes should return empty list."""
    state_data = {"search": {"keyword": "test"}}
    state_json = json.dumps(state_data)
    html = f'<script>window.__INITIAL_STATE__ = {state_json}</script>'
    url = "https://www.xiaohongshu.com/search"
    events = parse_initial_state(html, url)

    assert events == []


def test_parse_initial_state_malformed_json() -> None:
    """Malformed JSON should return empty list gracefully."""
    html = '<script>window.__INITIAL_STATE__ = {invalid json}</script>'
    url = "https://www.xiaohongshu.com/search"
    events = parse_initial_state(html, url)

    assert events == []


def test_parse_initial_state_truncation() -> None:
    """Test that long titles and descriptions are truncated."""
    long_title = "A" * 150
    long_desc = "B" * 400

    state_data = {
        "notes": [
            {
                "id": "123",
                "title": long_title,
                "desc": long_desc
            }
        ]
    }
    state_json = json.dumps(state_data)
    html = f'<script>window.__INITIAL_STATE__ = {state_json}</script>'
    url = "https://www.xiaohongshu.com/search"
    events = parse_initial_state(html, url)

    assert len(events) == 1
    # Event name should be truncated to 100 chars
    assert len(events[0].event_name) <= 100
    # Raw text should be truncated to 500 chars
    assert len(events[0].raw_text) <= 500


def test_parse_initial_state_trailing_semicolon() -> None:
    """Test handling of trailing semicolon in JSON."""
    state_data = {"notes": [{"id": "x", "title": "Test"}]}
    state_json = json.dumps(state_data)
    html = f'<script>window.__INITIAL_STATE__ = {state_json};</script>'
    url = "https://www.xiaohongshu.com/search"
    events = parse_initial_state(html, url)

    assert len(events) == 1
    assert events[0].event_name == "Test"
