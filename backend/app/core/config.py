from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://compa:compa@localhost:5432/compa"
    redis_url: str = "redis://localhost:6379"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    naver_client_id: str = ""
    naver_client_secret: str = ""
    amazon_access_key: str = ""
    amazon_secret_key: str = ""
    amazon_partner_tag: str = ""
    rakuten_app_id: str = ""
    rakuten_affiliate_id: str = ""
    coupang_partner_id: str = ""
    instagram_access_token: str = ""
    tiktok_client_key: str = ""
    premium_api_keys: str = ""
    proxy_pool_url: str = ""
    admin_secret: str | None = None
    allowed_origins: list[str] = ["http://localhost:5173"]
    # 로컬 AI (Ollama) 설정 — use_local_ai=True 시 Claude API 대신 Ollama 사용
    ollama_url: str = "http://localhost:11434"
    local_ai_model: str = "qwen2.5:14b"
    use_local_ai: bool = False
    # Firecrawl 스크래핑 서버
    firecrawl_url: str = "http://localhost:8765"
    firecrawl_extract_provider: str = "local"
    # 활성 스크래퍼 목록 (쉼표 구분, "all" 이면 전체)
    enabled_scrapers: str = "네이버쇼핑,Rakuten"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


settings = Settings()
