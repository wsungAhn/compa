from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str  # Required — no default, must be in .env
    redis_url: str = "redis://localhost:6379"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    naver_client_id: str = ""
    naver_client_secret: str = ""
    amazon_access_key: str = ""
    amazon_secret_key: str = ""
    amazon_partner_tag: str = ""
    instagram_access_token: str = ""
    tiktok_client_key: str = ""
    rakuten_app_id: str = ""
    proxy_pool_url: str = ""
    admin_secret: str | None = None
    allowed_origins: list[str] = ["http://localhost:5173"]
    # 로컬 AI (Ollama) 설정 — use_local_ai=True 시 Claude API 대신 Ollama 사용
    ollama_url: str = "http://localhost:11434"
    local_ai_model: str = "qwen2.5:14b"
    use_local_ai: bool = True
    # Firecrawl 스크래핑 서버
    firecrawl_url: str = "http://localhost:8765"
    firecrawl_extract_provider: str = "local"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",")]
        return v


settings = Settings()
