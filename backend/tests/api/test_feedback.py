import pytest
from pydantic import ValidationError
from unittest.mock import MagicMock

from app.api import feedback
from app.api.feedback import FeedbackIn


def test_feedback_payload_accepts_valid_input() -> None:
    payload = FeedbackIn(message="좋아요", contact="a@example.com", page="home")

    assert payload.message == "좋아요"
    assert payload.contact == "a@example.com"
    assert payload.page == "home"


def test_feedback_payload_rejects_empty_message() -> None:
    with pytest.raises(ValidationError):
        FeedbackIn(message="")


def test_feedback_payload_rejects_long_contact() -> None:
    with pytest.raises(ValidationError):
        FeedbackIn(message="x", contact="a" * 256)


def test_feedback_admin_secret_requires_configured_secret(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(feedback, "settings", MagicMock(admin_secret="secret"))

    assert feedback._is_authorized_feedback_secret("secret") is True
    assert feedback._is_authorized_feedback_secret("wrong") is False


def test_feedback_admin_secret_disabled_when_unset(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(feedback, "settings", MagicMock(admin_secret=None))

    assert feedback._is_authorized_feedback_secret("secret") is False
