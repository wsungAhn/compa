"""llama.cpp 로컬 AI 클라이언트 (httpx 기반, OpenAI 호환 API)."""
import logging
from typing import Any

import json
import httpx
from pathlib import Path

from app.core.config import settings


HERMES_SERVER_STATE = Path.home() / ".hermes/runtimes/llamacpp/server.json"


def llamacpp_headers() -> dict[str, str]:
    """Bearer header for the hermes-managed router (AH-061 §9); {} when the state file is absent."""
    try:
        key = json.loads(HERMES_SERVER_STATE.read_text(encoding="utf-8"))["api_key"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return {"Authorization": f"Bearer {key}"}


_logger = logging.getLogger(__name__)


def validate_backend(backend: str) -> None:
    if backend == "ollama":
        _logger.warning("Legacy ollama backend mapped to llama.cpp")
    elif backend != "llamacpp":
        raise ValueError("unsupported local AI backend")


def chat_url(base: str) -> str:
    from urllib.parse import urlsplit

    base = base.strip().rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.port == 11434:
        raise ValueError("invalid llama.cpp endpoint")
    if parsed.path not in ("", "/v1", "/v1/chat/completions") or parsed.query or parsed.fragment:
        raise ValueError("invalid llama.cpp endpoint path")
    if base.endswith("/v1/chat/completions"):
        return base
    return base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions")


async def local_chat(system: str, user: str) -> str:
    """로컬 OpenAI 호환 /v1/chat/completions 엔드포인트로 텍스트 생성.

    llama.cpp OpenAI-compatible API 사용.
    temperature=0.1로 설정 (구조화 JSON 출력에 최적).

    Args:
        system: 시스템 프롬프트 (비어있으면 전송 안 함)
        user: 사용자 메시지

    Returns:
        모델의 응답 텍스트. 오류 시 빈 문자열 반환 (예외 전파 금지).
    """
    try:
        # 메시지 구성
        messages = []
        if system.strip():
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        validate_backend(settings.local_ai_backend)
        base_url = chat_url(settings.llamacpp_url)
        model = settings.llamacpp_ai_model

        # OpenAI-compatible endpoint 호출
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                base_url,
                headers=llamacpp_headers(),
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.1,
                    "stream": False,
                    "max_tokens": 2048,
                    "reasoning_effort": "none",
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            )

        if response.status_code != 200:
            _logger.warning(
                f"llama.cpp API error {response.status_code}: {response.text[:200]}"
            )
            return ""

        result: dict[str, Any] = response.json()
        choices: list[Any] = result.get("choices", [{}])
        message: dict[str, Any] = choices[0].get("message", {}) if choices else {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty or invalid llama.cpp content")
        return content.strip()

    except httpx.ConnectError:
        _logger.error(
            f"llama.cpp 연결 실패: {settings.llamacpp_url}. "
            "로컬 서버가 실행 중인지 확인하세요 (llama-server)"
        )
        return ""
    except httpx.TimeoutException:
        _logger.error(
            f"llama.cpp 타임아웃 (60초). 큰 모델이거나 서버가 과부하 상태일 수 있습니다."
        )
        return ""
    except Exception as e:
        _logger.error(f"llama.cpp 호출 중 예외: {type(e).__name__}: {e}")
        return ""
