"""Record actionable errors into the incidents table so superadmin can
triage them without having to tail logs.

Kept deliberately tiny: one log() function, swallows its own errors so
we never break a user-facing flow because of a logging hiccup.
"""
from sqlalchemy.orm import Session

from app.models.incident import Incident


MAX_MESSAGE_LEN = 500
MAX_DETAILS_LEN = 4000


def log(
    db: Session,
    type: str,
    message: str,
    business_id: int | None = None,
    details: str = "",
) -> None:
    """Insert an incident row. Best-effort — any exception here is swallowed
    so the caller's flow (chat response, translation, email send) is
    never interrupted by a logging failure."""
    try:
        incident = Incident(
            business_id=business_id,
            type=type[:40],
            message=(message or "")[:MAX_MESSAGE_LEN],
            details=(details or "")[:MAX_DETAILS_LEN],
        )
        db.add(incident)
        db.commit()
    except Exception:
        # Never propagate — logging is non-critical
        try:
            db.rollback()
        except Exception:
            pass
