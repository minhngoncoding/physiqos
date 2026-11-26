from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Nutrients(BaseModel):
    calories: float = Field(ge=0)
    protein: float = Field(ge=0)
    carb: float = Field(ge=0)
    fat: float = Field(ge=0)


class FoodGroup(StrEnum):
    SINGLE_WITH_GRAMS = "A"  # 1 món, có gram
    SINGLE_HOUSEHOLD = "B"  # 1 món, đơn vị thường ngày
    MULTI_ITEM = "C"  # bữa nhiều món
    HARD = "D"  # khó / bẫy


class FoodItem(BaseModel):
    weight: float = Field(gt=0)
    food_name: str = Field(min_length=1)
    nutrient_per_100g: Nutrients
    source: Literal[
        "usda_foundation", "usda_sr_legacy", "usda_fndds", "vn_fct", "nutrition5k"
    ]
    source_id: str = Field(min_length=1)
    # e.g. ["ức gà", "chicken breast"].
    aliases: list[str] = Field(default_factory=list)


class LabeledMeal(BaseModel):
    """Fields and checks shared by every eval sample, whatever the input is."""

    id: str
    items: list[FoodItem]
    split: Literal["dev", "test"]
    tags: list[str]
    expected_needs_clarification: bool
    label: Nutrients
    label_notes: str | None = None
    labeled_by: str = Field(min_length=1)
    labeled_at: date

    @model_validator(mode="after")
    def check_label_matches_items(self):
        if (
            not self.items
            and not self.expected_needs_clarification
            and "non_food" not in self.tags
        ):
            raise ValueError("Không có món ăn")

        for name in Nutrients.model_fields:
            total_value = 0

            for food in self.items:
                per_100g = getattr(food.nutrient_per_100g, name)
                total_value += (per_100g * food.weight) / 100

            label_value = getattr(self.label, name)

            if abs(label_value - total_value) > 1:
                raise ValueError(
                    f"{name}: label={label_value}, calculate={total_value}"
                )

        return self


class TextMeal(LabeledMeal):
    id: str = Field(pattern=r"^t\d{3}$")
    modality: Literal["text"] = "text"
    lang: Literal["vi", "en", "mixed"]
    group: FoodGroup
    input: str = Field(min_length=2)


class ImageRef(BaseModel):
    path: str = Field(min_length=1)
    view: Literal["overhead", "angle_45"]
    source: Literal["nutrition5k", "ifpri_atlas", "self"]
    # Id in the source dataset: Nutrition5k "dish_<id>", IFPRI atlas
    # "atlas_<meal>_<portion>" (e.g. "atlas_065_M").
    dish_id: str | None = None

    @model_validator(mode="after")
    def check_dish_id(self):
        if self.source != "self" and not self.dish_id:
            raise ValueError(f"{self.source} image needs dish_id")
        return self


class ImageMeal(LabeledMeal):
    id: str = Field(pattern=r"^i\d{3}$")
    modality: Literal["image"]
    images: list[ImageRef] = Field(min_length=1)
    prompt: str | None = None  # optional text sent with the photo


Meal = TextMeal
