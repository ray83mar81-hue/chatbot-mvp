import json
import unicodedata

from sqlalchemy.orm import Session

from app.models.intent import Intent


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


def match_intent(user_message: str, db: Session, business_id: int) -> Intent | None:
    """
    Match user message against active intents using:
    1. Exact substring match (keyword found in message)
    2. Fuzzy match per word (handles typos like "horarioo", "precis")
    Returns the best matching intent or None.
    """
    intents = (
        db.query(Intent)
        .filter(Intent.business_id == business_id, Intent.is_active.is_(True))
        .order_by(Intent.priority.desc())
        .all()
    )

    normalized_msg = _normalize(user_message)
    msg_words = normalized_msg.split()

    best_match: Intent | None = None
    best_score = 0.0

    for intent in intents:
        keywords: list[str] = json.loads(intent.keywords)
        score = 0.0

        for kw in keywords:
            norm_kw = _normalize(kw)

            # 1) Exact substring match
            if norm_kw in normalized_msg:
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
            best_match = intent

    # Require a minimum score to avoid false positives
    if best_score < 1.0:
        return None

    return best_match
