from sqlalchemy import Column, Integer, String
from database import Base

class Menu(Base):
    __tablename__ = "menu"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, index=True)
    meal_type = Column(String, index=True)
    text = Column(String)
    dish_id = Column(Integer, nullable=True)
    servings = Column(Integer, default=1)

class Shopping(Base):
    __tablename__ = "shopping"
    id = Column(Integer, primary_key=True, index=True)
    item_text = Column(String)
    name = Column(String, index=True)
    quantity = Column(String)
    unit = Column(String)
    bought = Column(Integer, default=0)
    category = Column(String, default="")

class Dish(Base):
    __tablename__ = "dishes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, index=True)

class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True, index=True)
    dish_id = Column(Integer, index=True)
    name = Column(String, nullable=False)
    quantity = Column(String)
    unit = Column(String)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    unit = Column(String)
    category = Column(String, index=True)

class Favorite(Base):
    __tablename__ = "favorites"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    from_date = Column(String)
    to_date = Column(String)
    created_at = Column(String)
    data = Column(String)
