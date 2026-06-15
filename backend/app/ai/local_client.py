"""Ollama 로컬 AI 클라이언트 (httpx 기반, OpenAI 호환 API)."""
import logging
from typing import Any

import httpx

from app.core.config import settings

_logger = logging.getLogger(__name__)


async def local_chat(system: str, user: str) -> str:
    """Ollama /v1/chat/completions 엔드포인트로 텍스트 생성.

    Ollama 0.1.14+ OpenAI-compatible API 사용.
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

        # Ollama OpenAI-compatible endpoint 호출
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.ollama_url}/v1/chat/completions",
                json={
                    "model": settings.local_ai_model,
                    "messages": messages,
                    "temperature": 0.1,
                    "stream": False,
                },
            )

        if response.status_code != 200:
            _logger.warning(
                f"Ollama API error {response.status_code}: {response.text[:200]}"
            )
            return ""

        result: dict[str, Any] = response.json()
        choices: list[Any] = result.get("choices", [{}])
        message: dict[str, Any] = choices[0].get("message", {}) if choices else {}
        content: str = str(message.get("content", "") or "")
        return content.strip()

    except httpx.ConnectError:
        _logger.error(
            f"Ollama 연결 실패: {settings.ollama_url}. "
            "로컬 서버가 실행 중인지 확인하세요 (ollama serve)"
        )
        return ""
    except httpx.TimeoutException:
        _logger.error(
            f"Ollama 타임아웃 (60초). 큰 모델이거나 서버가 과부하 상태일 수 있습니다."
        )
        return ""
    except Exception as e:
        _logger.error(f"Ollama 호출 중 예외: {type(e).__name__}: {e}")
        return ""
