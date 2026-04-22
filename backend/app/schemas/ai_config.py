"""AI per-tenant configuration schemas (Fase 5)."""
from pydantic import BaseModel


AI_PROVIDER_CHOICES = ("openrouter", "openai", "anthropic", "gemini", "grok", "custom")


class AIConfigResponse(BaseModel):
    """Returned by GET. `api_key_masked` is the only hint of the key's value;
    the real key is never exposed via the API once stored.
    """
    provider: str | None
    model: str | None
    base_url: str | None
    api_key_masked: str  # "" if unset; "****abcd" otherwise
    has_api_key: bool
    input_price_per_million: float | None
    output_price_per_million: float | None


class AIConfigUpdate(BaseModel):
    """PATCH payload. Any field omitted is left unchanged.
    For `api_key`:
      - omit (None) to keep the existing key
      - send "" to explicitly clear it
      - send any other string to replace the key
    """
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    input_price_per_million: float | None = None
    output_price_per_million: float | None = None


class OpenRouterModel(BaseModel):
    id: str
    name: str
    context_length: int | None = None
    input_price_per_million: float | None = None
    output_price_per_million: float | None = None
