from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://compa:compa@localhost:5432/compa"
    redis_url: str = "redis://localhost:6379"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    ncp_api_key_id: str = ""
    ncp_api_key: str = ""
    amazon_access_key: str = ""
    amazon_secret_key: str = ""
    amazon_partner_tag: str = ""
    rakuten_app_id: str = ""
    rakuten_access_key: str = ""
    rakuten_affiliate_id: str = ""
    coupang_partner_id: str = ""
    instagram_access_token: str = ""
    tiktok_client_key: str = ""
    premium_api_keys: str = ""
    proxy_pool_url: str = ""
    admin_secret: str | None = None
    allowed_origins: list[str] = ["http://localhost:5173"]
    # 로컬 AI — legacy Ollama 필드는 설정 호환용이며 전송에 사용하지 않음
    local_ai_backend: str = "llamacpp"
    ollama_url: str = "http://localhost:11434"
    local_ai_model: str = "qwen2.5:14b"
    llamacpp_url: str = "http://127.0.0.1:18434"
    llamacpp_ai_model: str = "Qwen3.6-35B-A3B-UD-Q4_K_M"
    use_local_ai: bool = False
    # 번역 설정 — 일반 AI와 독립적인 llama.cpp endpoint/model
    translation_backend: str = "llamacpp"
    translation_ollama_url: str = "http://localhost:11434"
    local_translation_model: str = "translategemma:4b"
    translation_llamacpp_url: str = "http://127.0.0.1:18434"
    llamacpp_translation_model: str = "Qwen3.6-35B-A3B-UD-Q4_K_M"
    # Firecrawl 스크래핑 서버. Docker compose에서는 FIRECRAWL_URL=http://firecrawl-local:8765로 override.
    firecrawl_url: str = "http://localhost:8765"
    firecrawl_extract_provider: str = "local"
    # 활성 스크래퍼 목록 (쉼표 구분, "all" 이면 전체)
    # Live sources as of 2026-08-05: 네이버쇼핑(API 종료)·올리브영·Ulta는 죽었다.
    enabled_scrapers: str = "Sephora,Amazon US,Rakuten,brands"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


settings = Settings()
