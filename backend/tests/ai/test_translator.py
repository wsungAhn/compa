"""번역 계층의 모든 기능을 테스트한다."""
import inspect
import pytest
from unittest.mock import ANY, patch
import httpx

from app.ai.translator import (
    _build_translate_prompt,
    _call_translategemma,
    _looks_like_translation_failure,
    detect_language,
    translate_for_llm,
    translate_for_matching,
)


class TestBuildTranslatePrompt:
    def test_includes_japanese_language_name_and_text(self):
        """프롬프트에 Japanese (ja)와 원문이 포함되는지 확인."""
        prompt = _build_translate_prompt("75mL", "ja")
        assert "Japanese (ja)" in prompt
        assert "75mL" in prompt


class TestCallTranslategemma:
    @patch("httpx.post")
    def test_success_response_returns_translated_text(self, mock_post):
        """200 응답 + 번역 결과 → 문자열 반환."""
        with patch("app.ai.translator.settings") as mock_settings:
            from app.ai.translator import _build_translate_prompt

            mock_settings.translation_backend = "ollama"
            mock_settings.translation_ollama_url = "http://localhost:11434"
            mock_settings.local_translation_model = "translategemma:4b"
            mock_settings.translation_llamacpp_url = "http://127.0.0.1:8083"
            mock_settings.llamacpp_translation_model = "llama-translate"

            prompt = _build_translate_prompt(
                "SK-II フェイシャルトリートメント エッセンス 75mL", "ja"
            )
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": "SK-II Facial Treatment Essence, 75ml"}}]
            }
            mock_post.return_value.status_code = 200

            result = _call_translategemma(
                "SK-II フェイシャルトリートメント エッセンス 75mL", "ja"
            )
        assert result == "SK-II Facial Treatment Essence, 75ml"
        mock_post.assert_called_once_with(
            "http://127.0.0.1:8083/v1/chat/completions",
            headers=ANY,
            json={
                "model": "llama-translate",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "max_tokens": 2048,
                "reasoning_effort": "none",
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=60.0,
        )

    @patch("httpx.post")
    def test_llamacpp_backend_uses_chat_completions_shape(self, mock_post):
        """llama.cpp 분기는 OpenAI 호환 body/응답 shape를 사용해야 한다."""
        with patch("app.ai.translator.settings") as mock_settings:
            mock_settings.translation_backend = "llamacpp"
            mock_settings.translation_llamacpp_url = "http://127.0.0.1:8083"
            mock_settings.llamacpp_translation_model = "llama-translate"
            mock_settings.translation_ollama_url = "http://localhost:11434"
            mock_settings.local_translation_model = "translategemma:4b"

            prompt = _build_translate_prompt("SK-II フェイシャルトリートメント エッセンス 75mL", "ja")
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": "SK-II Facial Treatment Essence, 75ml"}}]
            }
            mock_post.return_value.status_code = 200

            result = _call_translategemma("SK-II フェイシャルトリートメント エッセンス 75mL", "ja")

        assert result == "SK-II Facial Treatment Essence, 75ml"
        mock_post.assert_called_once_with(
            "http://127.0.0.1:8083/v1/chat/completions",
            headers=ANY,
            json={
                "model": "llama-translate",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "max_tokens": 2048,
                "reasoning_effort": "none",
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=60.0,
        )

    def test_call_translategemma_stays_synchronous(self):
        assert inspect.iscoroutinefunction(_call_translategemma) is False

    @patch("httpx.post")
    def test_500_response_returns_none(self, mock_post):
        """500 응답 → None 반환."""
        mock_post.return_value.status_code = 500
        
        result = _call_translategemma("test", "ja")
        assert result is None

    @patch("httpx.post")
    def test_http_error_returns_none(self, mock_post):
        """HTTPError → None 반환 (예외 전파 없음)."""
        mock_post.side_effect = httpx.HTTPError("Connection error")

        result = _call_translategemma("test", "ja")
        assert result is None

    @patch("httpx.post")
    def test_malformed_json_response_returns_none(self, mock_post):
        """응답 바디가 깨진 JSON이어도 예외가 새지 않고 None 반환(리뷰 중 실측 발견 —
        랩탑이 재기동 중이면 빈/HTML 응답이 올 수 있다)."""
        import json

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.side_effect = json.JSONDecodeError("bad json", "doc", 0)

        result = _call_translategemma("test", "ja")
        assert result is None


class TestLooksLikeTranslationFailure:
    def test_same_as_original_returns_true(self):
        """출력=입력 → True."""
        result = _looks_like_translation_failure("SK-II 75mL", "SK-II 75mL", "ja")
        assert result is True

    def test_empty_string_returns_true(self):
        """빈 문자열 → True."""
        result = _looks_like_translation_failure("フェイシャル…", "", "ja")
        assert result is True

    def test_no_latin_characters_returns_true(self):
        """라틴 문자 없음 → True."""
        result = _looks_like_translation_failure("フェイシャル…", "フェイシャル…トリートメント", "ja")
        assert result is True

    def test_normal_translation_returns_false(self):
        """정상 번역 → False."""
        result = _looks_like_translation_failure("フェイシャル…", "Facial Treatment Essence", "ja")
        assert result is False


class TestTranslateForLLM:
    @patch("app.ai.translator._call_translategemma")
    def test_japanese_text_calls_translator_and_returns_result(self, mock_call):
        """ja 텍스트에 대해 모의 번역 결과를 반환."""
        mock_call.return_value = "Translated text"
        
        result = translate_for_llm("日本語のテキスト")
        assert result == "Translated text"
        mock_call.assert_called_once_with("日本語のテキスト", "ja")

    @patch("app.ai.translator._call_translategemma")
    def test_cached_text_does_not_call_translator_again(self, mock_call):
        """캐시된 텍스트에 대해 _call_translategemma를 다시 호출하지 않음."""
        # Clear cache at start of test to ensure clean state
        import app.ai.translator as translator_module
        translator_module._translation_cache.clear()
        
        # First call - should call translator and cache result
        mock_call.return_value = "Translated text"
        result1 = translate_for_llm("日本語のテキスト")
        assert result1 == "Translated text"
        assert mock_call.call_count == 1

        # Second call with same text - should use cache and not call translator again
        result2 = translate_for_llm("日本語のテキスト")
        assert result2 == "Translated text"
        assert mock_call.call_count == 1  # Should not increase

    @patch("app.ai.translator._call_translategemma")
    def test_english_text_does_not_call_translator(self, mock_call):
        """en 텍스트를 받으면 _call_translategemma를 호출하지 않고 원문 반환."""
        result = translate_for_llm("English text")
        assert result == "English text"
        mock_call.assert_not_called()

    @patch("app.ai.translator._call_translategemma")
    def test_none_from_translator_returns_original(self, mock_call):
        """_call_translategemma가 None을 반환하면 원문 반환(예외 없음)."""
        # Clear cache at start of test to ensure clean state
        import app.ai.translator as translator_module
        translator_module._translation_cache.clear()
        
        mock_call.return_value = None
        
        result = translate_for_llm("日本語のテキスト")
        assert result == "日本語のテキスト"


class TestTranslateForMatching:
    @patch("app.ai.translator.canonicalize_brand_mentions")
    @patch("app.ai.translator._call_translategemma")
    def test_calls_canonicalize_before_translation(self, mock_call, mock_canonical):
        """translate_for_matching이 canonicalize_brand_mentions를 거친 뒤 번역 호출."""
        mock_canonical.return_value = "SK-II Facial Treatment Essence"
        mock_call.return_value = "SK-II Facial Treatment Essence, 75ml"
        
        result = translate_for_matching("SK-II フェイシャルトリートメント エッセンス", "ja")
        
        mock_canonical.assert_called_once_with("SK-II フェイシャルトリートメント エッセンス")
        mock_call.assert_called_once_with("SK-II Facial Treatment Essence", "ja")
        assert result == "SK-II Facial Treatment Essence, 75ml"

    @patch("app.ai.translator._call_translategemma")
    def test_none_from_translator_returns_none(self, mock_call):
        """_call_translategemma가 None을 반환하면 None 반환."""
        mock_call.return_value = None
        
        result = translate_for_matching("日本語のテキスト", "ja")
        assert result is None

    @patch("app.ai.translator._call_translategemma")
    def test_failure_detection_returns_none(self, mock_call):
        """_looks_like_translation_failure가 True가 되는 경우 None 반환."""
        mock_call.return_value = "日本語のテキスト"  # Same as original
        
        result = translate_for_matching("日本語のテキスト", "ja")
        assert result is None

@pytest.mark.parametrize("content", [None, 42, {}, "   "])
def test_invalid_content_is_not_cached(content, monkeypatch, caplog):
    from app.ai import translator
    from unittest.mock import MagicMock
    translator._translation_cache.clear()
    response = MagicMock(status_code=200)
    response.json.return_value = {"choices": [{"message": {"content": content}}]}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: response)
    text = "日本語のテキスト"
    assert translate_for_llm(text) == text
    assert text not in translator._translation_cache
    assert "invalid content" in caplog.text


def test_unknown_backend_never_calls_transport(monkeypatch):
    from app.ai import translator
    monkeypatch.setattr(translator.settings, "translation_backend", "typo")
    with patch("httpx.post") as post:
        assert _call_translategemma("test", "ja") is None
        post.assert_not_called()
