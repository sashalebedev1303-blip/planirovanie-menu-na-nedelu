from pydantic import BaseModel

class MenuItemCreate(BaseModel):
    date: str
    meal_type: str
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
