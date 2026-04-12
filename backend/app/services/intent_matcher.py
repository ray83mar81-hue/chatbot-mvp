import json
import unicodedata

from sqlalchemy.orm import Session

from app.models.intent import Intent
from app.models.intent_translation import IntentTranslation


def _normalize(text: str) -> str:
    """Lowercase, strip accents, remove punctuation."""
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in nfkd if not unicodedata.combining(c))
    for ch in "¿?¡!.,;:\"'()[]{}":
        text = text.replace(ch, "")
    return text


def _similarity(a: str, b: str) -> float:
    """Simple character-level similarity ratio (0..1). No external deps."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Longest common subsequence length / max length
    m, n = len(a), len(b)
    if m > n:
        a, b = b, a
        m, n = n, m
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev = curr
    lcs = prev[n]
    return (2.0 * lcs) / (m + n)


# Thresholds
FUZZY_THRESHOLD = 0.75  # min similarity for fuzzy match
EXACT_WEIGHT = 2.0      # score boost for exact substring match
FUZZY_WEIGHT = 1.0      # score for fuzzy match


def match_intent(
    user_message: str,
    db: Session,
    business_id: int,
    language: str,
) -> tuple[Intent, IntentTranslation] | None:
    """
    Match user message against active intents in the requested language.

    Joins each Intent with its IntentTranslation in the given language and
    matches against the LOCALIZED keywords. Intents that don't have a
    translation in the requested language are skipped (the AI fallback,
    which is multilingual via system prompt, will handle them).

    Returns a (Intent, IntentTranslation) tuple so the caller can use the
    localized response and button label, plus the shared button_url.
    """
    rows = (
        db.query(Intent, IntentTranslation)
        .join(IntentTranslation, IntentTranslation.intent_id == Intent.id)
        .filter(
            Intent.business_id == business_id,
            Intent.is_active.is_(True),
            IntentTranslation.language_code == language,
        )
        .order_by(Intent.priority.desc())
        .all()
    )

    normalized_msg = _normalize(user_message)
    msg_words = normalized_msg.split()

    best_match: tuple[Intent, IntentTranslation] | None = None
    best_score = 0.0

    for intent, translation in rows:
        try:
            keywords: list[str] = json.loads(translation.keywords or "[]")
        except json.JSONDecodeError:
            continue

        score = 0.0

        for kw in keywords:
            norm_kw = _normalize(kw)

            # 1) Exact substring match
            if norm_kw and norm_kw in normalized_msg:
                score += EXACT_WEIGHT
                continue

            # 2) Fuzzy match: compare keyword against each word in message
            for word in msg_words:
                sim = _similarity(norm_kw, word)
                if sim >= FUZZY_THRESHOLD:
                    score += FUZZY_WEIGHT * sim
                    break  # count each keyword at most once

        if score > best_score:
            best_score = score
            best_match = (intent, translation)

    # Require a minimum score to avoid false positives
    if best_score < 1.0:
        return None

    return best_match
