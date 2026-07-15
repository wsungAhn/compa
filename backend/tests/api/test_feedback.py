import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock

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
    assert feedback._is_authorized_feedback_secret(None) is False


def test_feedback_admin_secret_disabled_when_unset(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(feedback, "settings", MagicMock(admin_secret=None))

    assert feedback._is_authorized_feedback_secret("secret") is False


def test_admin_feedback_rejects_missing_header(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(feedback, "settings", MagicMock(admin_secret="secret"))
    app = FastAPI()
    app.include_router(feedback.router)

    response = TestClient(app).get("/api/admin/feedback")

    assert response.status_code == 404


def test_admin_feedback_accepts_secret_header(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(feedback, "settings", MagicMock(admin_secret="secret"))

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    class DummySessionLocal:
        async def __aenter__(self) -> AsyncMock:
            return mock_session

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            return None

    monkeypatch.setattr(feedback, "AsyncSessionLocal", DummySessionLocal)
    app = FastAPI()
    app.include_router(feedback.router)

    response = TestClient(app).get(
        "/api/admin/feedback",
        headers={"X-Admin-Secret": "secret"},
    )

    assert response.status_code == 200
    assert response.json() == []
    mock_session.execute.assert_awaited_once()
