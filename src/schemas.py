from typing import Literal

from pydantic import BaseModel

# Форма «День меню» поддерживает ровно четыре приёма пищи (используются
# интерфейсом, фильтром и случайным меню). Другие значения — ошибка валидации
# (исправление баг-репорта ЛР-7 № 3: раньше сохранялось всё подряд).
MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]

class MenuItemCreate(BaseModel):
    date: str
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"]
    text: str = ""
    dish_id: int | None = None
    servings: int = 1

class ShoppingItemCreate(BaseModel):
    name: str
    quantity: str = ""
    unit: str = ""
    category: str = ""

class ShoppingItemUpdate(BaseModel):
    name: str | None = None
    quantity: str | None = None
    unit: str | None = None
    category: str | None = None
    bought: int | None = None

class DishIngredient(BaseModel):
    name: str
    quantity: str = ""
    unit: str = ""

class DishCreate(BaseModel):
    name: str
    category: str = ""
    ingredients: list[DishIngredient] = []

class ProductCreate(BaseModel):
    name: str
    unit: str = ""
    category: str = ""

class RandomMenuRequest(BaseModel):
    start_date: str
    days: int = 7

class DuplicateMenuRequest(BaseModel):
    from_date: str
    to_date: str
    overwrite: bool = False

class SaveFavoriteRequest(BaseModel):
    title: str
    from_date: str
    to_date: str

class ApplyFavoriteRequest(BaseModel):
    favorite_id: int
    to_date: str
    overwrite: bool = False
