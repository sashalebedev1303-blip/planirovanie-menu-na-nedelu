"""Модульные тесты агрегации списка покупок (ЛР-7).

Строки тестов перенесены из таблицы тест-дизайна
(docs/testing/test-design.md): сначала построили классы
эквивалентности и граничные значения, затем закодировали их здесь.
"""

from dataclasses import dataclass

import pytest

from shopping_calc import aggregate_ingredients, collect_servings, format_quantity


@dataclass
class MenuRow:
    """Имитация строки меню: логика читает только dish_id и servings."""

    dish_id: int | None = None
    servings: int = 1


@dataclass
class IngredientRow:
    """Имитация ингредиента из справочника блюд."""

    dish_id: int
    name: str
    quantity: str
    unit: str


def aggregate_one(quantity, servings=1, name="Молоко", unit="г", dish_id=1):
    """Хелпер: агрегация одного ингредиента одного блюда."""
    return aggregate_ingredients(
        {dish_id: servings},
        [IngredientRow(dish_id=dish_id, name=name, quantity=quantity, unit=unit)],
    )


# ============ collect_servings: расчёт порций блюд ============


def test_collect_servings_sums_same_dish_from_multiple_meals():
    # Блюдо 5 на обеде — 2 порции и на ужине — 3 порции
    rows = [MenuRow(dish_id=5, servings=2), MenuRow(dish_id=5, servings=3)]
    assert collect_servings(rows) == {5: 5}


def test_collect_servings_ignores_items_without_dish_id():
    # Текстовые позиции меню («Кофе») без связи со справочником не учитываются
    rows = [MenuRow(dish_id=None, servings=4), MenuRow(dish_id=7, servings=2)]
    assert collect_servings(rows) == {7: 2}


def test_collect_servings_treats_zero_servings_as_one():
    # Граница: servings=0 (не заполнено) не должно обнулять блюдо
    rows = [MenuRow(dish_id=3, servings=0), MenuRow(dish_id=3, servings=1)]
    assert collect_servings(rows) == {3: 2}


# ============ format_quantity: оформление числа ============


def test_format_quantity_integer_without_fraction():
    assert format_quantity(300.0) == "300"


def test_format_quantity_fraction_uses_comma():
    assert format_quantity(0.5) == "0,5"


# ============ aggregate_ingredients: классы эквивалентности количества ============


def test_aggregate_single_ingredient_times_servings():
    # «150 г» × 3 порции
    assert aggregate_one("150", servings=3) == [{"name": "Молоко", "unit": "г", "quantity": "450"}]


def test_aggregate_parses_comma_decimal():
    # «50,5» × 2 порции — запятая как десятичный разделитель
    assert aggregate_one("50,5", servings=2)[0]["quantity"] == "101"


def test_aggregate_fractional_quantity_formatted_with_comma():
    # «0,25» × 2 — дробный итог печатается с запятой, а не с точкой
    assert aggregate_one("0,25", servings=2)[0]["quantity"] == "0,5"


def test_aggregate_non_numeric_quantity_stays_text():
    # «по вкусу» складывать нельзя — указывается вместе с порциями
    assert aggregate_one("по вкусу", servings=2) == [
        {"name": "Молоко", "unit": "г", "quantity": "по вкусу (x2)"}
    ]


def test_aggregate_combines_numeric_and_text():
    # В одном блюде «100 г», в другом тот же ингредиент «по вкусу»
    rows = aggregate_ingredients(
        {1: 1, 2: 2},
        [
            IngredientRow(dish_id=1, name="Соль", quantity="100", unit="г"),
            IngredientRow(dish_id=2, name="соль", quantity="по вкусу", unit="г"),
        ],
    )
    assert rows == [{"name": "Соль", "unit": "г", "quantity": "100 (+ по вкусу (x2))"}]


def test_aggregate_empty_quantity_yields_empty_string():
    # Пустое количество не должно превращаться в «None» или «0»
    assert aggregate_one("", servings=1)[0]["quantity"] == ""


# ============ aggregate_ingredients: классы эквивалентности группировки ============


def test_aggregate_merges_same_ingredient_case_insensitive():
    # «Яйца» из двух блюд с разным регистром — одна позиция
    rows = aggregate_ingredients(
        {1: 1, 2: 1},
        [
            IngredientRow(dish_id=1, name="Яйца", quantity="3", unit="шт"),
            IngredientRow(dish_id=2, name="яйца", quantity="2", unit="шт"),
        ],
    )
    assert len(rows) == 1
    assert rows[0] == {"name": "Яйца", "unit": "шт", "quantity": "5"}


def test_aggregate_separates_different_units():
    # Одинаковый ингредиент в разных единицах не смешивается
    rows = aggregate_ingredients(
        {1: 1},
        [
            IngredientRow(dish_id=1, name="Мука", quantity="200", unit="г"),
            IngredientRow(dish_id=1, name="мука", quantity="300", unit="мл"),
        ],
    )
    assert [(r["name"], r["quantity"], r["unit"]) for r in rows] == [
        ("Мука", "200", "г"),
        ("мука", "300", "мл"),
    ]


def test_aggregate_strips_whitespace_from_name():
    assert aggregate_one("80", name="  Сыр  ")[0]["name"] == "Сыр"


def test_aggregate_skips_ingredients_not_on_menu():
    # Ингредиент блюда, которого нет в меню, в список не попадает
    rows = aggregate_ingredients(
        {1: 2},
        [
            IngredientRow(dish_id=1, name="Молоко", quantity="100", unit="мл"),
            IngredientRow(dish_id=99, name="Не в меню", quantity="50", unit="г"),
        ],
    )
    assert [r["name"] for r in rows] == ["Молоко"]


def test_aggregate_skips_blank_names():
    # Ингредиент без названия не создаёт пустую позицию в списке
    rows = aggregate_ingredients(
        {1: 1},
        [IngredientRow(dish_id=1, name="   ", quantity="10", unit="г")],
    )
    assert rows == []


# ============ параметризированный тест: граничные значения количества ============


@pytest.mark.parametrize(
    "quantity, servings, expected",
    [
        ("1", 1, "1"),          # минимум порций
        ("1", 2, "2"),
        ("0,5", 1, "0,5"),      # дробное без пересчёта
        ("0,5", 2, "1"),        # дробное × 2 = целое
        ("2,5", 4, "10"),       # граница целого
        ("0,1", 3, "0,3"),      # погрешность float не портит вывод
        ("500", 1, "500"),      # большое значение
    ],
)
def test_aggregate_quantity_boundaries(quantity, servings, expected):
    assert aggregate_one(quantity, servings=servings)[0]["quantity"] == expected
