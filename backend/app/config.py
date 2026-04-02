from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./chatbot.db"
    AI_PROVIDER: str = "anthropic"  # "anthropic" or "openai"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = ""
    OPENAI_API_KEY: str = ""
    AI_MODEL: str = "anthropic/claude-sonnet-4-20250514"
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440  # 24 hours
    CORS_ORIGINS: str = "*"

    model_config = {"env_file": ".env"}


settings = Settings()
