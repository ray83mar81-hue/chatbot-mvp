from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://user:pass@localhost:5432/chatbot"

    # AI provider selection. "openai" uses the OpenAI-compatible endpoint
    # (works with OpenRouter, Together, Groq, or OpenAI directly) and unlocks
    # cheaper models like gpt-4o-mini, gemini-2.5-flash, llama-3.3.
    # "anthropic" keeps the legacy Anthropic SDK path for Claude-only access.
    AI_PROVIDER: str = "openai"  # "openai" | "anthropic"
    AI_MODEL: str = "openai/gpt-4o-mini"

    # OpenAI / OpenRouter
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Anthropic (legacy path)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = ""
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440  # 24 hours
    CORS_ORIGINS: str = "*"

    # SMTP for contact form email notifications (leave empty to skip sending)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_TLS: bool = True

    # Salt for hashing client IPs (GDPR compliance)
    IP_HASH_SALT: str = "change-me-in-production"

    # On startup, if an AdminUser with this email exists, promote it to
    # role=superadmin. Useful for one-shot deployments where the existing
    # admin user should become the platform operator.
    SUPERADMIN_EMAIL: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
