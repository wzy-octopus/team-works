from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite+aiosqlite:///./app.db"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24時間

    # CORS: カンマ区切りで複数指定可 (例: http://localhost:5173,https://myapp.azurewebsites.net)
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    # LLM backend: "foundry" (Azure AI Foundry) or "direct" (Anthropic API直接)
    LLM_BACKEND: str = "foundry"
    FOUNDRY_API_KEY: str = ""
    FOUNDRY_ENDPOINT: str = ""
    FOUNDRY_MODEL: str = "claude-sonnet-4-5"
    ANTHROPIC_API_KEY: str = ""


settings = Settings()
