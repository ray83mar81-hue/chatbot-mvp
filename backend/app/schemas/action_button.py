from pydantic import BaseModel


class ActionButtonTranslationIn(BaseModel):
    language_code: str
    label: str = ""


class ActionButtonTranslationOut(BaseModel):
    language_code: str
    label: str

    model_config = {"from_attributes": True}


class ActionButtonCreate(BaseModel):
    type: str
    value: str = ""
    icon: str = ""
    open_new_tab: bool = True
    priority: int = 0
    is_active: bool = True
    translations: list[ActionButtonTranslationIn] = []


class ActionButtonUpdate(BaseModel):
    type: str | None = None
    value: str | None = None
    icon: str | None = None
    open_new_tab: bool | None = None
    priority: int | None = None
    is_active: bool | None = None
    # When present, replaces the entire translations set for the button.
    translations: list[ActionButtonTranslationIn] | None = None


class ActionButtonAdmin(BaseModel):
    id: int
    business_id: int
    type: str
    value: str
    icon: str
    open_new_tab: bool
    priority: int
    is_active: bool
    translations: list[ActionButtonTranslationOut] = []

    model_config = {"from_attributes": True}


class ActionButtonPublic(BaseModel):
    """Shape served to the widget: flat, single language already resolved."""
    id: int
    type: str
    value: str
    icon: str
    label: str
    open_new_tab: bool
