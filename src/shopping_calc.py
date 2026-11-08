"""Агрегация ингредиентов меню в список покупок (ЛР-7).

До ЛР-7 эта логика находилась внутри маршрута /api/shopping/generate
(main.py): транспортный слой FastAPI сам считал суммарные порции блюд,
складывал одинаковые ингредиенты и форматировал количества. Модуль
выделен по SRP — теперь логику можно тестировать без запуска
приложения и БД (так же, как в ЛР-6 был выделен parse_quantity).
"""

from quantity import parse_quantity


def collect_servings(menu_items):
    """Считает суммарное число порций каждого блюда из позиций меню.

    :param menu_items: строки меню (объекты с полями ``dish_id`` и ``servings``)
    :return: dict ``{dish_id: суммарное число порций}``
    """
    dish_servings = {}
    for item in menu_items:
        if item.dish_id:
            dish_servings[item.dish_id] = dish_servings.get(item.dish_id, 0) + (item.servings or 1)
    return dish_servings


def format_quantity(q):
    """Форматирует количество как число для интерфейса.

    Целые выводятся без дробной части («300»), дробные — с запятой в
    качестве десятичного разделителя («0,5»), как принято во всём UI.
    """
    if q == int(q):
        return str(int(q))
    return f"{q:g}".replace(".", ",")


def aggregate_ingredients(dish_servings, ingredients):
    """Собирает сводный список покупок.

    Одинаковые ингредиенты (имя + единица, без учёта регистра) суммы
    считаются вместе; количество масштабируется на суммарное число
    порций блюда. Нечисловые количества («по вкусу») не складываются,
    а перечисляются с указанием порций.

    :param dish_servings: dict ``{dish_id: порции}``, см. :func:`collect_servings`
    :param ingredients: ингредиенты, относящиеся к блюдам из меню
    :return: список dict ``{name, unit, quantity}`` (в порядке первого появления)
    """
    aggregated = {}
    for ing in ingredients:
        servings = dish_servings.get(ing.dish_id)
        if servings is None:
            # ингредиент блюда, которого нет в меню, в список не попадает
            continue

        name = (ing.name or "").strip()
        unit = (ing.unit or "").strip()
        if not name:
            continue

        key = (name.lower(), unit.lower())
        qty_num, qty_text = parse_quantity(ing.quantity)

        bucket = aggregated.setdefault(key, {
            "name": name,
            "unit": unit,
            "qty": 0.0,
            "has_numeric": False,
            "text_qty": [],
        })

        if qty_num is not None:
            bucket["qty"] += qty_num * servings
            bucket["has_numeric"] = True
        elif qty_text:
            bucket["text_qty"].append(f"{qty_text} (x{servings})")

    rows = []
    for bucket in aggregated.values():
        if bucket["has_numeric"]:
            qty_str = format_quantity(bucket["qty"])
            if bucket["text_qty"]:
                qty_str += " (+ " + ", ".join(bucket["text_qty"]) + ")"
        else:
            qty_str = ", ".join(bucket["text_qty"])

        rows.append({
            "name": bucket["name"],
            "unit": bucket["unit"],
            "quantity": qty_str,
        })
    return rows
