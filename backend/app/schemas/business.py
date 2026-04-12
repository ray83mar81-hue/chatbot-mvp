from datetime import datetime

from pydantic import BaseModel, EmailStr


class BusinessBase(BaseModel):
    name: str
    description: str = ""
    schedule: str = "{}"  # JSON string
    address: str = ""
    phone: str = ""
    email: str = ""
    extra_info: str = ""
    supported_languages: str = '["es"]'  # JSON list of language codes
    default_language: str = "es"
    welcome_messages: str = "{}"  # JSON {lang_code: text}
    # Contact form
    contact_form_enabled: bool = False
    contact_notification_email: str = ""
    privacy_url: str = ""
    whatsapp_phone: str = ""
    whatsapp_enabled: bool = False


class BusinessCreate(BusinessBase):
    pass


class BusinessUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    schedule: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    extra_info: str | None = None
    supported_languages: str | None = None
    default_language: str | None = None
    welcome_messages: str | None = None
    # Contact form
    contact_form_enabled: bool | None = None
    contact_notification_email: str | None = None
    privacy_url: str | None = None
    whatsapp_phone: str | None = None
    whatsapp_enabled: bool | None = None


class BusinessResponse(BusinessBase):
    id: int
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}
