from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    database_url: str = "postgresql+asyncpg://omni:omnipass@localhost:5432/omnisupport"
    otel_service_name: str = "tool_api"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    release_id: str = "dev-local"

    # HITL 配置
    hitl_webhook_url: str = ""   # Week10 接入
    hitl_timeout_sec: int = 300


settings = Settings()
