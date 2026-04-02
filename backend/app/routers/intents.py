from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.intent import Intent
from app.schemas.intent import IntentCreate, IntentResponse, IntentUpdate

router = APIRouter(prefix="/intents", tags=["intents"])


@router.get("/", response_model=list[IntentResponse])
def list_intents(business_id: int = 1, db: Session = Depends(get_db)):
    return (
        db.query(Intent)
        .filter(Intent.business_id == business_id)
        .order_by(Intent.priority.desc())
        .all()
    )


@router.get("/{intent_id}", response_model=IntentResponse)
def get_intent(intent_id: int, db: Session = Depends(get_db)):
    intent = db.query(Intent).filter(Intent.id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")
    return intent


@router.post("/", response_model=IntentResponse)
def create_intent(data: IntentCreate, db: Session = Depends(get_db)):
    intent = Intent(**data.model_dump())
    db.add(intent)
    db.commit()
    db.refresh(intent)
    return intent


@router.put("/{intent_id}", response_model=IntentResponse)
def update_intent(
    intent_id: int, data: IntentUpdate, db: Session = Depends(get_db)
):
    intent = db.query(Intent).filter(Intent.id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(intent, key, value)

    db.commit()
    db.refresh(intent)
    return intent


@router.delete("/{intent_id}")
def delete_intent(intent_id: int, db: Session = Depends(get_db)):
    intent = db.query(Intent).filter(Intent.id == intent_id).first()
    if not intent:
        raise HTTPException(status_code=404, detail="Intent not found")
    db.delete(intent)
    db.commit()
    return {"detail": "Intent deleted"}
