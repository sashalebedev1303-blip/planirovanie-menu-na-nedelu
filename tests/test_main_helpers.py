"""Модульные тесты хелперов, выделенных при рефакторинге ЛР-8.

Реестр технического долга ЛР-8 (docs/lab8/tech-debt-registry.md):
* Д-2 — replace_ingredients (общий код create_dish/update_dish);
* Д-4 — pick_dish_for_meal (выбор случайного блюда без повтора за день).

Тесты страхуют рефакторинг: интеграционные тесты ЛР-7 проверяют маршруты
сквозь API, эти — логику хелперов напрямую.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine

from database import Base
from main import Ingredient, Product, pick_dish_for_meal, replace_ingredients
from schemas import DishIngredient


@pytest.fixture()
def db():
    """Чистая in-memory БД со схемой проекта."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    from sqlalchemy.orm import sessionmaker
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_replace_ingredients_saves_rows_and_skips_empty_names(db):
    """Д-2: ингредиенты сохраняются, пустые имена пропускаются."""
    replace_ingredients(db, dish_id=1, ingredients=[
        DishIngredient(name="Соль", quantity="10", unit="г"),
        DishIngredient(name="", quantity="5", unit="г"),  # пустое имя — мимо
    ])
    rows = db.query(Ingredient).filter(Ingredient.dish_id == 1).all()
    assert [r.name for r in rows] == ["Соль"]
    assert rows[0].quantity == "10"

    # побочный эффект: ингредиент попал в справочник продуктов
    assert db.query(Product).filter(Product.name == "Соль").count() == 1


def test_replace_ingredients_empty_list(db):
    """Д-2: пустой список ингредиентов не создаёт строк и не падает."""
    replace_ingredients(db, dish_id=2, ingredients=[])
    assert db.query(Ingredient).filter(Ingredient.dish_id == 2).count() == 0


def test_pick_dish_does_not_repeat_during_the_day():
    """Д-4: за один день блюдо не повторяется, пока есть неповторённые."""
    by_cat = {"lunch": [SimpleNamespace(id=1), SimpleNamespace(id=2)]}
    used = set()
    first = pick_dish_for_meal(by_cat, "lunch", used)
    second = pick_dish_for_meal(by_cat, "lunch", used)
    assert first.id != second.id


def test_pick_dish_allows_repeat_when_category_exhausted():
    """Д-4: если блюда категории закончились — допускается повтор."""
    by_cat = {"snack": [SimpleNamespace(id=7)]}
    used = {7}
    dish = pick_dish_for_meal(by_cat, "snack", used)
    assert dish.id == 7
