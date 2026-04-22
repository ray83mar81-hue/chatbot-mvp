"""Per-tenant AI configuration endpoints (Fase 5).

The tenant owner (or superadmin) configures provider + model + API key for
their business. When nothing is configured, the chat service falls back to
the global env vars so existing deployments keep working.
"""
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import assert_business_write, get_current_user
from app.models.admin_user import AdminUser
from app.models.business import Business
from app.schemas.ai_config import (
    AI_PROVIDER_CHOICES,
    AIConfigResponse,
    AIConfigUpdate,
    OpenRouterModel,
)

router = APIRouter(tags=["ai-config"])


def _mask_key(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 4:
        return "****"
    return "****" + key[-4:]


def _build_response(biz: Business) -> AIConfigResponse:
    return AIConfigResponse(
        provider=biz.ai_provider,
        model=biz.ai_model,
        base_url=biz.ai_base_url,
        api_key_masked=_mask_key(biz.ai_api_key),
        has_api_key=bool(biz.ai_api_key),
        input_price_per_million=biz.ai_input_price_per_million,
        output_price_per_million=biz.ai_output_price_per_million,
    )


@router.get(
    "/business/{business_id}/ai-config",
    response_model=AIConfigResponse,
)
def get_ai_config(
    business_id: int,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_business_write(current, business_id)
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return _build_response(business)


@router.patch(
    "/business/{business_id}/ai-config",
    response_model=AIConfigResponse,
)
def update_ai_config(
    business_id: int,
    data: AIConfigUpdate,
    current: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assert_business_write(current, business_id)
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    payload = data.model_dump(exclude_unset=True)

    if "provider" in payload:
        p = (payload["provider"] or "").strip().lower() or None
        if p is not None and p not in AI_PROVIDER_CHOICES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid provider '{p}'. Valid: {', '.join(AI_PROVIDER_CHOICES)}",
            )
        business.ai_provider = p

    if "model" in payload:
        m = (payload["model"] or "").strip()
        business.ai_model = m or None

    if "api_key" in payload:
        # None → unchanged (handled by exclude_unset above; "api_key" is in
        # payload only if the caller sent it explicitly).
        # "" → clear
        # any other string → replace
        k = payload["api_key"]
        if k == "":
            business.ai_api_key = None
        elif k is not None:
            business.ai_api_key = k.strip() or None

    if "base_url" in payload:
        u = (payload["base_url"] or "").strip()
        business.ai_base_url = u or None

    if "input_price_per_million" in payload:
        v = payload["input_price_per_million"]
        business.ai_input_price_per_million = (
            float(v) if v is not None and v != "" else None
        )

    if "output_price_per_million" in payload:
        v = payload["output_price_per_million"]
        business.ai_output_price_per_million = (
            float(v) if v is not None and v != "" else None
        )

    db.commit()
    db.refresh(business)
    return _build_response(business)


# ── OpenRouter models proxy ────────────────────────────────────────────

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_OPENROUTER_CACHE_TTL = 3600  # seconds
_openrouter_cache: dict = {"expires_at": 0.0, "data": []}


def _price_per_million(v) -> float | None:
    """OpenRouter returns USD-per-token as strings. Convert to per-million."""
    try:
        return float(v) * 1_000_000
    except (TypeError, ValueError):
        return None


@router.get("/ai/openrouter-models", response_model=list[OpenRouterModel])
async def list_openrouter_models(
    _: AdminUser = Depends(get_current_user),
):
    """List all models available on OpenRouter. Cached in-memory for 1h.
    Authenticated: any logged-in admin (owner or superadmin) can query this
    to populate the model dropdown.
    """
    now = time.time()
    if now < _openrouter_cache["expires_at"] and _openrouter_cache["data"]:
        return _openrouter_cache["data"]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(_OPENROUTER_MODELS_URL)
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenRouter fetch failed: {e}")

    raw = r.json().get("data") or []
    out: list[OpenRouterModel] = []
    for m in raw:
        pricing = m.get("pricing") or {}
        out.append(OpenRouterModel(
            id=m.get("id") or "",
            name=m.get("name") or m.get("id") or "",
            context_length=m.get("context_length"),
            input_price_per_million=_price_per_million(pricing.get("prompt")),
            output_price_per_million=_price_per_million(pricing.get("completion")),
        ))

    _openrouter_cache["data"] = out
    _openrouter_cache["expires_at"] = now + _OPENROUTER_CACHE_TTL
    return out
