"""Tests for search endpoint schema and collection guard logic."""
from uuid import uuid4

from app.api.products import _should_schedule
from app.api.schemas import ProductSummary, SearchOut


def test_search_out_serializes_correctly() -> None:
    """Test SearchOut schema validation and serialization."""
    summary = ProductSummary(
        id=uuid4(),
        name_kr="에센스",
        name_en="Essence",
        name_jp=None,
        name_cn=None,
        brand="COMPA",
        category="base",
    )

    out = SearchOut(products=[summary], collecting=False)
    assert out.collecting is False
    assert len(out.products) == 1
    assert out.products[0].name_kr == "에센스"

    # Test serialization to dict
    out_dict = out.model_dump()
    assert out_dict["collecting"] is False
    assert len(out_dict["products"]) == 1


def test_search_out_with_collecting_true() -> None:
    """Test SearchOut with collecting flag true."""
    out = SearchOut(products=[], collecting=True)
    assert out.collecting is True
    assert len(out.products) == 0


def test_should_schedule_guards_duplicates() -> None:
    """Test _should_schedule prevents duplicate concurrent collections."""
    # Clear state
    from app.api.products import _collecting_queries

    _collecting_queries.clear()

    # First call should schedule
    assert _should_schedule("test_query") is True
    assert "test_query" in _collecting_queries

    # Second call for same query should not schedule
    assert _should_schedule("test_query") is False
    assert "test_query" in _collecting_queries

    # Different query should schedule
    assert _should_schedule("other_query") is True
    assert "other_query" in _collecting_queries

    # Clean up
    _collecting_queries.clear()
