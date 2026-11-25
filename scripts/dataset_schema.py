from datetime import date
from enum import StrEnum
from typing import Literal, Optional
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
    # Allowed label sources, see "Label sources" in data/README.md.
    # Adding a source = update README (license) + DATACARD too.
    source: Literal["usda_foundation", "usda_sr_legacy", "usda_fndds", "vn_fct"]
    source_id: str = Field(min_length=1)


class Meal(BaseModel):
    id: str = Field(pattern=r"^t\d{3}$")
    lang: Literal["vi", "en", "mixed"]
    group: FoodGroup
    input: str = Field(min_length=2)
    items: list[FoodItem]
    split: Literal["dev", "test"]
    tags: list[str]
    expected_needs_clarification: bool
    label: Nutrients
    label_notes: Optional[str] = None
    labeled_by: str = Field(min_length=1)
    labeled_at: date

    @model_validator(mode="after")
    def check_label_matches_items(self):
        # Empty items are allowed only when the model should ask back, or when
        # the input is not food at all (label is then all zero).
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
