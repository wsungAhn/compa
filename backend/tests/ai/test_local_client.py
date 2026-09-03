"""Tests for the local AI chat client backend selection."""
from unittest.mock import AsyncMock, MagicMock, patch

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
            json={
                "model": "llama-chat",
                "messages": [
                    {"role": "system", "content": "system prompt"},
                    {"role": "user", "content": "user prompt"},
                ],
                "temperature": 0.1,
                "stream": False,
            },
        )

    @patch("app.ai.local_client.httpx.AsyncClient")
    async def test_default_backend_keeps_ollama_url_and_model(
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
            "http://localhost:11434/v1/chat/completions",
            json={
                "model": "qwen2.5:14b",
                "messages": [{"role": "user", "content": "user prompt"}],
                "temperature": 0.1,
                "stream": False,
            },
        )
