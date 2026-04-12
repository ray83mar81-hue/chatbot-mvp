from datetime import datetime

from pydantic import BaseModel, EmailStr


class ContactSubmit(BaseModel):
    """Public payload from the widget contact form."""
    business_id: int = 1
    session_id: str = ""         # to link with conversation if any
    name: str
    phone: str
    email: EmailStr
    message: str
    language: str = "es"
    whatsapp_opt_in: bool = False
    privacy_accepted: bool
    honeypot: str = ""           # anti-spam: must be empty


class ContactRequestResponse(BaseModel):
    id: int
    business_id: int
    conversation_id: int | None
    name: str
    phone: str
    email: str
    message: str
    whatsapp_opt_in: bool
    privacy_accepted: bool
    language: str
    status: str
    notes: str
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class ContactRequestUpdate(BaseModel):
    """Admin payload to change status or add notes."""
    status: str | None = None
    notes: str | None = None


class ContactConfigResponse(BaseModel):
    """Public payload the widget uses to decide whether to show the form."""
    contact_form_enabled: bool
    whatsapp_enabled: bool
    privacy_url: str
    # Per-language overrides: {lang_code: {privacy_url, contactTitle, contactName, ...}}
    translations: dict[str, dict] = {}
