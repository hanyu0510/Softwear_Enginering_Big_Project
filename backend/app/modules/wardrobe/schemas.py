from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Category(StrEnum):
    tops = "tops"
    bottoms = "bottoms"
    outerwear = "outerwear"
    dress = "dress"
    shoes = "shoes"
    bag = "bag"
    accessory = "accessory"
    other = "other"


class Season(StrEnum):
    spring = "spring"
    summer = "summer"
    autumn = "autumn"
    winter = "winter"


class Style(StrEnum):
    minimal = "minimal"
    street = "street"
    sweet = "sweet"
    formal = "formal"
    casual = "casual"
    vintage = "vintage"
    sporty = "sporty"


class Occasion(StrEnum):
    commute = "commute"
    date = "date"
    travel = "travel"
    casual = "casual"
    formal = "formal"
    party = "party"
    sport = "sport"


class Visibility(StrEnum):
    private = "private"
    public = "public"


class ItemFields(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    name: str = Field(min_length=1, max_length=120)
    category: Category | None = None
    color: str | None = Field(default=None, min_length=1, max_length=32)
    colors: list[str] = Field(default_factory=list, max_length=8)
    warmth: int | None = Field(default=None, ge=1, le=5)
    material: str | None = Field(default=None, max_length=80)
    pattern: str | None = Field(default=None, max_length=80)
    season: list[Season] = Field(default_factory=list, max_length=4)
    style: list[Style] = Field(default_factory=list, max_length=7)
    occasion: list[Occasion] = Field(default_factory=list, max_length=7)
    visibility: Visibility = Visibility.private

    @field_validator("name", "color", "material", "pattern")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class ItemCreate(ItemFields):
    image_file_id: str = Field(alias="imageFileId", min_length=1, max_length=40)


class ItemPatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: Category | None = None
    color: str | None = Field(default=None, min_length=1, max_length=32)
    colors: list[str] | None = Field(default=None, max_length=8)
    warmth: int | None = Field(default=None, ge=1, le=5)
    material: str | None = Field(default=None, max_length=80)
    pattern: str | None = Field(default=None, max_length=80)
    season: list[Season] | None = Field(default=None, max_length=4)
    style: list[Style] | None = Field(default=None, max_length=7)
    occasion: list[Occasion] | None = Field(default=None, max_length=7)
    visibility: Visibility | None = None
    is_favorite: bool | None = None

    @field_validator("name", "color", "material", "pattern")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class RecognizeRequest(BaseModel):
    image_file_id: str = Field(alias="imageFileId", min_length=1, max_length=40)

    model_config = ConfigDict(populate_by_name=True)


class WishCreate(BaseModel):
    source_item_id: str = Field(min_length=1, max_length=40)


class DictResponse(BaseModel):
    categories: list[str]
    seasons: list[str]
    styles: list[str]
    occasions: list[str]
    visibility: list[str]


def wardrobe_dict() -> dict:
    return {
        "categories": [entry.value for entry in Category],
        "seasons": [entry.value for entry in Season],
        "styles": [entry.value for entry in Style],
        "occasions": [entry.value for entry in Occasion],
        "visibility": [entry.value for entry in Visibility],
    }
