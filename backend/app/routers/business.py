from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.business import Business
from app.schemas.business import BusinessCreate, BusinessResponse, BusinessUpdate

router = APIRouter(prefix="/business", tags=["business"])


@router.get("/{business_id}", response_model=BusinessResponse)
def get_business(business_id: int, db: Session = Depends(get_db)):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


@router.post("/", response_model=BusinessResponse)
def create_business(data: BusinessCreate, db: Session = Depends(get_db)):
    business = Business(**data.model_dump())
    db.add(business)
    db.commit()
    db.refresh(business)
    return business


@router.put("/{business_id}", response_model=BusinessResponse)
def update_business(
    business_id: int, data: BusinessUpdate, db: Session = Depends(get_db)
):
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(business, key, value)

    db.commit()
    db.refresh(business)
    return business
