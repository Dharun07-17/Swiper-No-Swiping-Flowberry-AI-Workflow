from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Flowberry API"
    environment: str = "dev"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg2://flowberry:flowberry@postgres:5432/flowberry"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    jwt_secret: str = "change_me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7

    fernet_key: str = "change_me_32_byte_base64_key"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    ollama_url: str | None = "http://ollama:11434"
    ollama_model: str = "llama2"

    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"
    public_base_url: str = "http://localhost:8000"
    frontend_public_url: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
