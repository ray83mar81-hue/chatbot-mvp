from pydantic import BaseModel


class LanguageResponse(BaseModel):
    code: str
    name: str
    native_name: str
    flag_emoji: str
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class WidgetUITexts(BaseModel):
    """Per-language widget UI texts."""
    title: str = ""
    subtitle: str = ""
    placeholder: str = ""


class BusinessLanguagesResponse(BaseModel):
    """Public payload the widget uses to render the language selector."""
    business_id: int
    default_language: str
    supported: list[LanguageResponse]              # full metadata of supported langs
    welcome_messages: dict[str, str] = {}          # {lang_code: welcome_text}
    widget_ui_texts: dict[str, WidgetUITexts] = {}  # {lang_code: {title, subtitle, placeholder}}


class BusinessLanguagesUpdate(BaseModel):
    """Admin payload to change which languages a business supports."""
    supported_languages: list[str] | None = None   # e.g. ["es","en","ca"]
    default_language: str | None = None
    welcome_messages: dict[str, str] | None = None
    widget_ui_texts: dict[str, WidgetUITexts] | None = None
