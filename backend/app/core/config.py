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
    instagram_access_token: str = ""
    tiktok_client_key: str = ""
    proxy_pool_url: str = ""


settings = Settings()
