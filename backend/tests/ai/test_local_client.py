"""Tests for the local AI chat client backend selection."""
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from app.ai.local_client import local_chat


@pytest.mark.asyncio
class TestLocalChat:
    @patch("app.ai.local_client.httpx.AsyncClient")
    async def test_llamacpp_backend_uses_llamacpp_base_url_and_model(
        self, mock_async_client
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "translated text"}}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client

        with patch("app.ai.local_client.settings") as mock_settings:
            mock_settings.local_ai_backend = "llamacpp"
            mock_settings.llamacpp_url = "http://127.0.0.1:8082"
            mock_settings.llamacpp_ai_model = "llama-chat"
            mock_settings.ollama_url = "http://localhost:11434"
            mock_settings.local_ai_model = "qwen2.5:14b"

            result = await local_chat("system prompt", "user prompt")

        assert result == "translated text"
        mock_client.post.assert_awaited_once_with(
            "http://127.0.0.1:8082/v1/chat/completions",
            headers=ANY,
            json={
                "model": "llama-chat",
                "messages": [
                    {"role": "system", "content": "system prompt"},
                    {"role": "user", "content": "user prompt"},
                ],
                "temperature": 0.1,
                "stream": False,
                "max_tokens": 2048,
                "reasoning_effort": "none",
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )

    @patch("app.ai.local_client.httpx.AsyncClient")
    async def test_legacy_backend_maps_to_llamacpp(
        self, mock_async_client
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ollama text"}}]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.__aenter__.return_value = mock_client

        with patch("app.ai.local_client.settings") as mock_settings:
            mock_settings.local_ai_backend = "ollama"
            mock_settings.ollama_url = "http://localhost:11434"
            mock_settings.local_ai_model = "qwen2.5:14b"
            mock_settings.llamacpp_url = "http://127.0.0.1:8082"
            mock_settings.llamacpp_ai_model = "llama-chat"

            result = await local_chat("", "user prompt")

        assert result == "ollama text"
        mock_client.post.assert_awaited_once_with(
            "http://127.0.0.1:8082/v1/chat/completions",
            headers=ANY,
            json={
                "model": "llama-chat",
                "messages": [{"role": "user", "content": "user prompt"}],
                "temperature": 0.1,
                "stream": False,
                "max_tokens": 2048,
                "reasoning_effort": "none",
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )

@pytest.mark.parametrize("base", ["http://localhost:8088", "http://localhost:8088/v1/", "http://localhost:8088/v1/chat/completions"])
def test_chat_endpoint_normalization(base):
    from app.ai.local_client import chat_url
    assert chat_url(base) == "http://localhost:8088/v1/chat/completions"

@pytest.mark.parametrize("base", ["", "http://localhost:11434/v1", "http://localhost:8088/api/generate"])
def test_chat_endpoint_rejects_stale_or_invalid(base):
    from app.ai.local_client import chat_url
    with pytest.raises(ValueError):
        chat_url(base)

@pytest.mark.asyncio
@pytest.mark.parametrize("content", [None, 12, {}, " "])
async def test_invalid_chat_content_returns_empty(content, monkeypatch):
    from app.ai import local_client
    response = MagicMock(status_code=200)
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    with patch("app.ai.local_client.httpx.AsyncClient") as client:
        client.return_value.__aenter__.return_value.post = AsyncMock(return_value=response)
        assert await local_chat("", "hello") == ""
