import json
import unicodedata

from sqlalchemy.orm import Session

from app.models.intent import Intent


def _normalize(text: str) -> str:
    """Lowercase, strip accents, remove punctuation."""
    text = text.lower().strip()
    # Remove accents: é → e, ñ → n, etc.
    nfkd = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Remove common punctuation
    for ch in "¿?¡!.,;:\"'()[]{}":
        text = text.replace(ch, "")
    return text


def match_intent(user_message: str, db: Session, business_id: int) -> Intent | None:
    """
    Try to match the user message against active intents.
    Returns the best matching intent or None.
    """
    intents = (
        db.query(Intent)
        .filter(Intent.business_id == business_id, Intent.is_active.is_(True))
        .order_by(Intent.priority.desc())
        .all()
    )

    normalized_msg = _normalize(user_message)
    best_match: Intent | None = None
    best_score = 0

    for intent in intents:
        keywords: list[str] = json.loads(intent.keywords)
        score = 0
        for kw in keywords:
            if _normalize(kw) in normalized_msg:
                score += 1

        # Require at least 1 keyword match
        if score > best_score:
            best_score = score
            best_match = intent

    return best_match
