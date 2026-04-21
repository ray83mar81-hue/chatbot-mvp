from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ActionButtonTranslation(Base):
    __tablename__ = "action_button_translations"
    __table_args__ = (
        UniqueConstraint("action_button_id", "language_code", name="uq_btn_lang"),
    )

    id = Column(Integer, primary_key=True, index=True)
    action_button_id = Column(
        Integer,
        ForeignKey("action_buttons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language_code = Column(
        String(5), ForeignKey("languages.code"), nullable=False, index=True
    )
    label = Column(String(100), nullable=False, default="")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    action_button = relationship("ActionButton", back_populates="translations")
