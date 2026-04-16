"""Chat gate: suspension, rate limiting and monthly token quota.

All three checks run before the actual AI call. If any fails, the chat
engine short-circuits and returns a user-facing message explaining why.
"""
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.conversation import Conversation
from app.models.message import Message


# Per-session rate limit (in-memory; resets on process restart).
# If you run multiple API replicas this becomes per-replica — move to Redis
# when that happens.
_session_hits: dict[str, list[float]] = defaultdict(list)
SESSION_LIMIT_WINDOW = 3600   # seconds
SESSION_LIMIT_COUNT = 60      # messages per session per window

# Per-business hourly rate limit (stops a runaway bot from flooding one tenant).
_business_hits: dict[int, list[float]] = defaultdict(list)
BUSINESS_LIMIT_WINDOW = 3600
BUSINESS_LIMIT_COUNT = 1000


@dataclass
class GateResult:
    ok: bool
    reason: str | None = None            # short machine code
    message: str | None = None           # user-facing text
    http_status: int = 200               # suggested status for non-streaming path


def _prune(entries: list[float], window: int) -> list[float]:
    cutoff = time.time() - window
    return [t for t in entries if t > cutoff]


def _month_start_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def tokens_used_this_month(db: Session, business_id: int) -> int:
    since = _month_start_utc()
    total = (
        db.query(func.coalesce(func.sum(Message.tokens_in + Message.tokens_out), 0))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            Conversation.business_id == business_id,
            Message.created_at >= since,
        )
        .scalar()
    ) or 0
    return int(total)


def check_chat_gate(
    business: Business, session_id: str, db: Session, language: str = "es"
) -> GateResult:
    """Run suspension + rate + quota checks in order. Short-circuits on first
    failure. Only counts successful attempts against the rate limits so that
    suspended / quota-exceeded clients don't use up rate budget too.
    """
    # Fallback messages per language — keep them short and generic so we don't
    # leak implementation details to end-users.
    msgs = {
        "suspended": {
            "es": "Este chat está temporalmente fuera de servicio. Contacta con el negocio directamente.",
            "en": "This chat is temporarily unavailable. Please contact the business directly.",
            "ca": "Aquest xat està temporalment fora de servei. Contacta amb el negoci directament.",
            "fr": "Ce chat est temporairement indisponible. Veuillez contacter directement l'entreprise.",
            "de": "Dieser Chat ist vorübergehend nicht verfügbar. Bitte wenden Sie sich direkt an das Unternehmen.",
            "it": "Questa chat è temporaneamente non disponibile. Contatta direttamente l'attività.",
            "pt": "Este chat está temporariamente indisponível. Contacta o negócio diretamente.",
        },
        "rate": {
            "es": "Has enviado demasiados mensajes en poco tiempo. Espera un momento antes de continuar.",
            "en": "Too many messages in a short period. Please wait a moment before continuing.",
            "ca": "Has enviat massa missatges en poc temps. Espera un moment abans de continuar.",
            "fr": "Trop de messages en peu de temps. Veuillez patienter un instant.",
            "de": "Zu viele Nachrichten in kurzer Zeit. Bitte warten Sie einen Moment.",
            "it": "Troppi messaggi in poco tempo. Attendi un momento.",
            "pt": "Demasiadas mensagens num curto período. Aguarda um momento antes de continuar.",
        },
        "quota": {
            "es": "El asistente ha alcanzado su límite mensual. Por favor, contacta directamente con el negocio.",
            "en": "The assistant has reached its monthly limit. Please contact the business directly.",
            "ca": "L'assistent ha arribat al seu límit mensual. Contacta directament amb el negoci.",
            "fr": "L'assistant a atteint sa limite mensuelle. Veuillez contacter directement l'entreprise.",
            "de": "Der Assistent hat sein monatliches Limit erreicht. Bitte kontaktieren Sie das Unternehmen direkt.",
            "it": "L'assistente ha raggiunto il limite mensile. Contatta direttamente l'attività.",
            "pt": "O assistente atingiu o limite mensal. Contacta o negócio diretamente.",
        },
    }

    def _msg(key: str) -> str:
        return msgs[key].get(language) or msgs[key]["es"]

    # 1) Suspension
    if not bool(business.is_active):
        return GateResult(ok=False, reason="suspended", message=_msg("suspended"), http_status=403)

    # 2) Rate limit per session
    if session_id:
        hits = _prune(_session_hits[session_id], SESSION_LIMIT_WINDOW)
        if len(hits) >= SESSION_LIMIT_COUNT:
            _session_hits[session_id] = hits  # persist pruned list
            return GateResult(ok=False, reason="rate_session", message=_msg("rate"), http_status=429)

    # 3) Rate limit per business
    biz_hits = _prune(_business_hits[business.id], BUSINESS_LIMIT_WINDOW)
    if len(biz_hits) >= BUSINESS_LIMIT_COUNT:
        _business_hits[business.id] = biz_hits
        return GateResult(ok=False, reason="rate_business", message=_msg("rate"), http_status=429)

    # 4) Monthly token quota
    quota = business.monthly_token_quota
    if quota is not None and quota > 0:
        used = tokens_used_this_month(db, business.id)
        if used >= quota:
            return GateResult(ok=False, reason="quota", message=_msg("quota"), http_status=429)

    # All checks passed — record the hit
    now = time.time()
    _session_hits[session_id].append(now)
    _business_hits[business.id].append(now)
    return GateResult(ok=True)
