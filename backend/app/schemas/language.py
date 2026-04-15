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


class WidgetDesign(BaseModel):
    """Global widget appearance (not per-language)."""
    color: str = "#2563eb"
    position: str = "right"            # "right" | "left"
    width: int = 380
    height: int = 540
    icon_type: str = "default"         # "default" | "emoji" | "image"
    bubble_emoji: str = ""
    bubble_image: str = ""


class BusinessLanguagesResponse(BaseModel):
    """Public payload the widget uses to render the language selector."""
    business_id: int
    default_language: str
    supported: list[LanguageResponse]              # full metadata of supported langs
    welcome_messages: dict[str, str] = {}          # {lang_code: welcome_text}
    widget_ui_texts: dict[str, WidgetUITexts] = {}  # {lang_code: {title, subtitle, placeholder}}
    widget_design: WidgetDesign = WidgetDesign()


class BusinessLanguagesUpdate(BaseModel):
    """Admin payload to change which languages a business supports."""
    supported_languages: list[str] | None = None   # e.g. ["es","en","ca"]
    default_language: str | None = None
    welcome_messages: dict[str, str] | None = None
    widget_ui_texts: dict[str, WidgetUITexts] | None = None
    widget_design: WidgetDesign | None = None
