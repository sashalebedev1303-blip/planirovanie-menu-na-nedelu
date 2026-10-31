import csv
import json
import random
from datetime import date as date_cls, timedelta, datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from pydantic import BaseModel

from database import BASE_DIR, Base, SessionLocal, engine
from export_strategies import get_strategy
from models import Menu, Shopping, Dish, Ingredient, Product, Favorite
from quantity import parse_quantity
from schemas import (
    MenuItemCreate, ShoppingItemCreate, ShoppingItemUpdate, DishIngredient,
    DishCreate, ProductCreate, RandomMenuRequest, DuplicateMenuRequest,
    SaveFavoriteRequest, ApplyFavoriteRequest
)

# ==================== ИНИЦИАЛИЗАЦИЯ БД ====================

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Проверяем, существует ли колонка servings, и добавляем её при необходимости
        # (для совместимости со старыми БД)
        try:
            db.execute(text("SELECT servings FROM menu LIMIT 1"))
        except Exception:
            print("[init_db] Добавление колонки 'servings' в таблицу 'menu'...")
            db.execute(text("ALTER TABLE menu ADD COLUMN servings INTEGER DEFAULT 1"))
            db.commit()

        count = db.execute(text("SELECT COUNT(*) FROM menu")).scalar()
        if count == 0:
            today = date_cls.today().isoformat()
            default_menu = [
                (today, "breakfast", "Омлет с сыром", 1, 1),
                (today, "lunch",     "Куриный суп",   4, 1),
                (today, "dinner",    "Пюре с котлетой", 8, 1),
                (today, "snack",     "Фрукты",        11, 1),
            ]
            for d, meal, txt, dish_id, servings in default_menu:
                db.execute(text(
                    "INSERT INTO menu (date, meal_type, text, dish_id, servings) VALUES (:d, :m, :t, :did, :s)"
                ), {"d": d, "m": meal, "t": txt, "did": dish_id, "s": servings})
            db.commit()

        dish_count = db.execute(text("SELECT COUNT(*) FROM dishes")).scalar()
        if dish_count == 0:
            csv_path = BASE_DIR / "dishes.csv"
            if not csv_path.exists():
                print(f"[init_db] ВНИМАНИЕ: файл {csv_path} не найден. Справочник пуст.")
            else:
                dishes_map = {}
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        dish_name = (row.get("dish_name") or "").strip()
                        category  = (row.get("category") or "").strip()
                        if not dish_name:
                            continue
                        if dish_name not in dishes_map:
                            db.execute(text(
                                "INSERT INTO dishes (name, category) VALUES (:n, :c)"
                            ), {"n": dish_name, "c": category})
                            db.commit()
                            new_id = db.execute(text("SELECT last_insert_rowid()")).scalar()
                            dishes_map[dish_name] = new_id
                        dish_id = dishes_map[dish_name]
                        ing_name = (row.get("ingredient_name") or "").strip()
                        if ing_name:
                            db.execute(text(
                                "INSERT INTO ingredients (dish_id, name, quantity, unit) "
                                "VALUES (:d, :n, :q, :u)"
                            ), {
                                "d": dish_id,
                                "n": ing_name,
                                "q": (row.get("quantity") or "").strip(),
                                "u": (row.get("unit") or "").strip()
                            })
                db.commit()
                print(f"[init_db] Загружено блюд из CSV: {len(dishes_map)}")

        product_count = db.execute(text("SELECT COUNT(*) FROM products")).scalar()
        if product_count == 0:
            default_products = [
                ("Картофель", "г", "Овощи"), ("Морковь", "г", "Овощи"),
                ("Лук", "г", "Овощи"), ("Помидоры", "г", "Овощи"),
                ("Огурцы", "г", "Овощи"), ("Капуста", "г", "Овощи"),
                ("Свекла", "г", "Овощи"), ("Перец болгарский", "г", "Овощи"),
                ("Кабачки", "г", "Овощи"), ("Баклажаны", "г", "Овощи"),
                ("Чеснок", "г", "Овощи"), ("Яблоки", "г", "Овощи"),
                ("Бананы", "г", "Фрукты"), ("Апельсины", "г", "Фрукты"),
                ("Лимоны", "г", "Фрукты"), ("Курица", "г", "Мясо"),
                ("Говядина", "г", "Мясо"), ("Свинина", "г", "Мясо"),
                ("Фарш", "г", "Мясо"), ("Бекон", "г", "Мясо"),
                ("Колбаса", "г", "Мясо"), ("Индейка", "г", "Мясо"),
                ("Рыба", "г", "Рыба"), ("Скумбрия", "г", "Рыба"),
                ("Сельдь", "г", "Рыба"), ("Лосось", "г", "Рыба"),
                ("Молоко", "мл", "Молочное"), ("Кефир", "мл", "Молочное"),
                ("Сметана", "г", "Молочное"), ("Творог", "г", "Молочное"),
                ("Сыр", "г", "Молочное"), ("Масло сливочное", "г", "Молочное"),
                ("Йогурт", "г", "Молочное"), ("Рис", "г", "Крупы"),
                ("Гречка", "г", "Крупы"), ("Манка", "г", "Крупы"),
                ("Овсянка", "г", "Крупы"), ("Перловка", "г", "Крупы"),
                ("Пшено", "г", "Крупы"), ("Макароны", "г", "Крупы"),
                ("Спагетти", "г", "Крупы"), ("Мука", "г", "Крупы"),
                ("Яйца", "шт", "Яйца"), ("Сахар", "г", "Прочее"),
                ("Соль", "г", "Прочее"), ("Масло растительное", "мл", "Прочее"),
                ("Грибы", "г", "Прочее"), ("Орехи", "г", "Прочее"),
                ("Мёд", "г", "Прочее"),
            ]
            for p_name, p_unit, p_cat in default_products:
                db.execute(text(
                    "INSERT INTO products (name, unit, category) VALUES (:n, :u, :c)"
                ), {"n": p_name, "u": p_unit, "c": p_cat})
            db.commit()
            print(f"[init_db] Загружено продуктов: {len(default_products)}")

        existing_names = {row[0].lower() for row in db.execute(text("SELECT name FROM products")).fetchall()}
        ingredients = db.execute(text("SELECT DISTINCT name FROM ingredients")).fetchall()
        added = 0
        for (ing_name,) in ingredients:
            if not ing_name:
                continue
            if ing_name.strip().lower() not in existing_names:
                db.execute(text(
                    "INSERT INTO products (name, unit, category) VALUES (:n, :u, :c)"
                ), {"n": ing_name.strip(), "u": "", "c": "Импорт"})
                added += 1
        if added:
            db.commit()
            print(f"[init_db] Добавлено продуктов из ингредиентов: {added}")
    finally:
        db.close()


init_db()

app = FastAPI(title="Помощник для планирования меню на неделю")





# ==================== ГЛАВНАЯ HTML-СТРАНИЦА ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    html = r'''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🍽️ Помощник для планирования меню на неделю</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/choices.js/public/assets/styles/choices.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
               font-size: 16px; padding: 15px; background-color: #f5f5f5; color: #333; }
        .dark-mode { background-color: #1a1a1a; color: #e0e0e0; }
        .dark-mode .menu-table { background-color: #2a2a2a; border-color: #444; }
        .dark-mode .menu-table th, .dark-mode .menu-table td { background-color: #333; border-color: #444; color: #e0e0e0; }
        .dark-mode .btn { background-color: #444; color: #e0e0e0; border-color: #555; }
        .dark-mode .choices__inner, .dark-mode .choices__list--dropdown,
        .dark-mode .choices__list--dropdown .choices__item { background-color: #2a2a2a; color: #e0e0e0; border-color: #444; }
        .dark-mode .choices__input { background-color: #2a2a2a; color: #e0e0e0; }
        .dark-mode .modal-content { background-color: #2a2a2a; color: #e0e0e0; }
        .dark-mode .modal-content p { color: #aaa; }
        .dark-mode .ingredient-row input { background-color: #333; color: #e0e0e0; border-color: #555; }
        .dark-mode .shop-input { background:#333; color:#e0e0e0; border-color:#555; }
        h1 { text-align: center; margin-bottom: 15px; }
        .controls { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; justify-content: center; }
        .btn { padding: 12px 20px; font-size: 16px; border: none; border-radius: 8px; cursor: pointer;
               background-color: #1976d2; color: white; min-width: 140px; }
        .btn:hover { background-color: #1565c0; }
        .btn-delete { background-color: #d32f2f; }
        .btn-delete:hover { background-color: #c62828; }
        .btn-add { background-color: #388e3c; min-width: auto; }
        .btn-add:hover { background-color: #2e7d32; }
        .btn-small { padding: 8px 16px; font-size: 14px; min-width: auto; }
        .btn-cancel { background-color: #999; }
        .btn-cancel:hover { background-color: #777; }
        .btn-ok { background-color: #388e3c; }
        .btn-ok:hover { background-color: #2e7d32; }
        .theme-toggle { background-color: #ff9800; }
        .theme-toggle:hover { background-color: #f57c00; }
        .menu-table { width: 100%; max-width: 1200px; margin: 0 auto 20px; border-collapse: collapse;
                      background-color: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .dark-mode .menu-table { box-shadow: 0 2px 8px rgba(0,0,0,0.3); }
        .menu-table th, .menu-table td { padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0; }
        .menu-table th { background-color: #1976d2; color: white; }
        .menu-table td:first-child { background-color: #e3f2fd; font-weight: 600; }
        .dark-mode .menu-table td:first-child { background-color: #1a237e; color: #9fa8da; }
        .day-controls { display: flex; justify-content: center; align-items: center; gap: 8px; }
        .empty-state { text-align: center; padding: 30px; color: #999; }
        .dark-mode .empty-state { color: #777; }
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                         background: rgba(0,0,0,0.6); z-index: 1000; justify-content: center; align-items: center; }
        .modal-overlay.active { display: flex; }
        .modal-content { background: white; padding: 25px; border-radius: 12px; max-width: 400px; width: 90%;
                         text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        .modal-content h2 { margin-bottom: 15px; }
        .modal-content p { margin-bottom: 20px; color: #666; }
        .modal-buttons { display: flex; flex-direction: column; gap: 10px; }
        @media (max-width: 600px) {
            .btn { padding: 10px 14px; font-size: 14px; }
            .menu-table th, .menu-table td { padding: 6px 3px; font-size: 13px; }
        }
        .menu-table .choices { margin: 0; }
        .menu-table .choices__inner { padding: 6px 8px; font-size: 15px; border-radius: 4px;
                                      min-height: 38px; background-color: white; }
        .menu-table .choices__list--single { padding: 2px 4px; }
        .menu-table .choices__list--dropdown { z-index: 100; }
        .dish-cell { display: flex; align-items: center; gap: 4px; }
        .dish-cell .choices { flex: 1; min-width: 0; }
        .btn-clear-dish { flex-shrink: 0; width: 28px; height: 28px; padding: 0; font-size: 12px;
                          background: #d32f2f; color: white; border: none; border-radius: 4px;
                          cursor: pointer; opacity: 0.7; }
        .btn-clear-dish:hover { opacity: 1; background: #c62828; }
        .ingredient-row { display: flex; gap: 6px; margin-bottom: 6px; align-items: center; }
        .ingredient-row input { padding: 8px; font-size: 14px; border: 1px solid #ddd; border-radius: 4px; }
        .ingredient-row input.ing-name { flex: 2; }
        .ingredient-row input.ing-qty  { flex: 1; max-width: 100px; }
        .ingredient-row input.ing-unit { flex: 1; max-width: 100px; }
        .ingredient-row button { padding: 8px 12px; font-size: 14px; background: #d32f2f;
                                 color: white; border: none; border-radius: 4px; cursor: pointer; }
        .ingredient-row button:hover { background: #c62828; }
        .btn-dup-day { flex-shrink: 0; width: 28px; height: 28px; padding: 0; font-size: 12px;
                       background: #6a1b9a; color: white; border: none; border-radius: 4px;
                       cursor: pointer; opacity: 0.7; }
        .btn-dup-day:hover { opacity: 1; background: #4a148c; }
        .fav-item { display: flex; justify-content: space-between; align-items: center;
                    background: #f5f5f5; padding: 10px 12px; border-radius: 6px; margin-bottom: 8px; }
        .dark-mode .fav-item { background: #333; }
        .fav-item strong { display: block; }
        .fav-item small { color: #888; }

        /* === Список покупок === */
        .shop-row { display: grid; grid-template-columns: 2fr 1fr 1fr auto auto; gap: 8px; align-items: center; }
        .shop-table { width: 100%; border-collapse: collapse; }
        .shop-table th, .shop-table td { padding: 8px 6px; border-bottom: 1px solid #e0e0e0; text-align: left; }
        .dark-mode .shop-table th, .dark-mode .shop-table td { border-color: #444; }
        .shop-table tr.bought td { text-decoration: line-through; color: #888;
                                   background: rgba(56,142,60,0.12); }
        .shop-input { padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; width: 100%; }
        .shop-actions { display: flex; gap: 4px; }
        .shop-check { width: 20px; height: 20px; cursor: pointer; }
        .shop-header-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }

        /* Стиль для поля ввода порций */
        .servings-input {
            width: 50px;
            padding: 6px;
            text-align: center;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 15px;
        }
        .dark-mode .servings-input {
            background: #333;
            color: #e0e0e0;
            border-color: #555;
        }
    </style>
</head>
<body>
    <h1>🍽️ Помощник для планирования меню на неделю</h1>

    <div class="controls">
        <input type="date" id="newDayDate" class="btn" style="padding: 10px; min-width: auto;">
        <button class="btn btn-add" onclick="addDay()">+ Добавить день</button>
        <button class="btn" onclick="openRandomModal()" style="background:#8e24aa;">🎲 Случайное меню</button>
        <button class="btn" onclick="openAddDishModal()">🍳 Добавить блюдо</button>
        <button class="btn" onclick="openDishesModal()">📚 Справочник блюд</button>
        <button class="btn" onclick="openProductsModal()">🥕 Справочник продуктов</button>
        <button class="btn" onclick="openFavoritesModal()" style="background:#f57f17;">⭐ Избранное</button>
        <button class="btn" onclick="openSaveFavoriteModal()" style="background:#ef6c00;">💾 Сохранить в избранное</button>
        <button class="btn" onclick="openShoppingModal()" style="background:#00897b;">📝 Список покупок</button>
        <button class="btn" onclick="clearAll()">🗑️ Очистить</button>
        <button class="btn theme-toggle" onclick="toggleTheme()">🌑/☀️</button>
    </div>

    <div class="controls">
        <label style="display:flex; align-items:center; gap:8px;">
            <strong>Фильтр по категории:</strong>
            <select id="categoryFilter" onchange="onCategoryFilter(this.value)"
                    style="padding: 10px; border-radius: 8px; border: 1px solid #ddd; font-size: 16px;">
                <option value="">Все категории</option>
                <option value="breakfast">Только завтраки</option>
                <option value="lunch">Только обеды</option>
                <option value="dinner">Только ужины</option>
                <option value="snack">Только перекусы</option>
            </select>
        </label>
    </div>

    <table class="menu-table" id="menuTable">
        <thead>
            <tr>
                <th>Дата</th>
                <th>День недели</th>
                <th>Завтрак</th>
                <th>Обед</th>
                <th>Ужин</th>
                <th>Перекус</th>
                <th title="Количество порций для каждого приема пищи">Порции</th> <!-- НОВАЯ КОЛОНКА -->
                <th>Действия</th>
            </tr>
        </thead>
        <tbody id="menuBody"></tbody>
    </table>

    <datalist id="productsDatalist"></datalist>

    <!-- Модалка: список покупок -->
    <div id="shoppingModal" class="modal-overlay">
        <div class="modal-content" style="max-width: 900px; text-align: left; max-height: 88vh; overflow-y: auto;">
            <h2 style="text-align: center;">📝 Список покупок</h2>
            <div class="shop-header-actions">
                <button class="btn btn-small" style="background:#00897b;" onclick="generateShoppingFromMenu()">
                    🔄 Сформировать из меню
                </button>
                <button class="btn btn-small btn-add" onclick="showAddShoppingForm()">➕ Добавить позицию</button>
                <button class="btn btn-small" style="background:#1976d2;" onclick="copyShoppingList()">
                    📋 Скопировать список к покупке
                </button>
                <button class="btn btn-small" style="background:#5e35b1;" onclick="downloadShoppingList()">
                    💾 Скачать .txt
                </button>
                <button class="btn btn-small" style="background:#2e7d32;" onclick="downloadShoppingCSV()">
                    📊 Скачать в CSV (Excel)
                </button>
                <button class="btn btn-small" style="background:#6a1b9a;" onclick="printShoppingList()">
                    🖨️ Печать отчёта
                </button>
                <button class="btn btn-small btn-delete" onclick="clearShoppingList()">🗑️ Очистить список</button>
            </div>
            <p style="font-size:13px; color:#888; margin-bottom:10px;">
                Отметка «куплено» визуально выделяет позицию и исключает её из итогового списка к покупке.
            </p>

            <!-- Форма добавления -->
            <div id="shopForm" style="display:none; background:#e0f2f1; padding:12px; border-radius:8px; margin-bottom:12px;">
                <strong id="shopFormTitle">Новая позиция</strong>
                <div style="display:flex; gap:8px; margin-top:8px; flex-wrap:wrap;">
                    <input type="text" id="shopFormName" class="shop-input" placeholder="Название" style="flex:2; min-width:180px;">
                    <input type="text" id="shopFormQty"  class="shop-input" placeholder="Кол-во" style="flex:1; min-width:80px;">
                    <input type="text" id="shopFormUnit" class="shop-input" placeholder="Ед." style="flex:1; min-width:80px;">
                    <input type="text" id="shopFormCat"  class="shop-input" placeholder="Категория" style="flex:1; min-width:120px;">
                </div>
                <div style="margin-top:8px; display:flex; gap:8px;">
                    <button class="btn btn-small btn-add" onclick="saveShopForm()">💾 Сохранить</button>
                    <button class="btn btn-small btn-cancel" onclick="hideShopForm()">❌ Отмена</button>
                </div>
            </div>

            <div id="shoppingListContainer"></div>

            <div class="modal-buttons" style="margin-top: 20px;">
                <button class="btn btn-cancel" onclick="closeShoppingModal()">❌ Закрыть</button>
            </div>
        </div>
    </div>

    <!-- Модалка: случайное меню -->
    <div id="randomModal" class="modal-overlay">
        <div class="modal-content" style="max-width: 480px; text-align: left;">
            <h2 style="text-align: center;">🎲 Генерация случайного меню</h2>
            <label style="display:block; margin: 10px 0;">
                <strong>Дата начала недели</strong>
                <input type="date" id="randomStartDate"
                       style="width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px;">
            </label>
            <label style="display:block; margin: 10px 0;">
                <strong>Количество дней</strong>
                <input type="number" id="randomDays" value="7" min="1" max="30"
                       style="width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px;">
            </label>
            <p style="font-size:13px; color:#888;">
                Система подберёт случайные блюда по категориям. Существующие дни в диапазоне будут перезаписаны.
            </p>
            <div class="modal-buttons" style="margin-top: 20px;">
                <button class="btn" onclick="doGenerateRandom()" style="background:#8e24aa;">🎲 Сгенерировать</button>
                <button class="btn btn-cancel" onclick="closeRandomModal()">❌ Отмена</button>
            </div>
        </div>
    </div>

    <!-- Модалка: дублирование дня -->
    <div id="duplicateModal" class="modal-overlay">
        <div class="modal-content" style="max-width: 480px; text-align: left;">
            <h2 style="text-align: center;">📋 Дублирование дня</h2>
            <p style="margin: 10px 0;">Копируем меню с <strong id="dupFromLabel">—</strong> на:</p>
            <label style="display:block; margin: 10px 0;">
                <strong>Целевая дата</strong>
                <input type="date" id="dupToDate"
                       style="width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px;">
            </label>
            <label style="display:block; margin: 10px 0;">
                <input type="checkbox" id="dupOverwrite"> Перезаписать, если на целевой дате уже есть блюда
            </label>
            <div class="modal-buttons" style="margin-top: 20px;">
                <button class="btn" onclick="doDuplicateDay()" style="background:#6a1b9a;">📋 Скопировать</button>
                <button class="btn btn-cancel" onclick="closeDuplicateModal()">❌ Отмена</button>
            </div>
        </div>
    </div>

    <!-- Модалка: сохранить в избранное -->
    <div id="saveFavModal" class="modal-overlay">
        <div class="modal-content" style="max-width: 520px; text-align: left;">
            <h2 style="text-align: center;">💾 Сохранить меню в избранное</h2>
            <label style="display:block; margin: 10px 0;">
                <strong>Название шаблона *</strong>
                <input type="text" id="favTitle" placeholder="Например: «Летнее меню»"
                       style="width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px;">
            </label>
            <label style="display:block; margin: 10px 0;">
                <strong>С даты</strong>
                <input type="date" id="favFromDate"
                       style="width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px;">
            </label>
            <label style="display:block; margin: 10px 0;">
                <strong>По дату</strong>
                <input type="date" id="favToDate"
                       style="width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px;">
            </label>
            <p style="font-size:13px; color:#888;">
                Меню за указанный диапазон будет сохранено как шаблон. Его можно будет применить к любой дате.
            </p>
            <div class="modal-buttons" style="margin-top: 20px;">
                <button class="btn" onclick="doSaveFavorite()" style="background:#ef6c00;">💾 Сохранить</button>
                <button class="btn btn-cancel" onclick="closeSaveFavoriteModal()">❌ Отмена</button>
            </div>
        </div>
    </div>

    <!-- Модалка: избранное -->
    <div id="favoritesModal" class="modal-overlay">
        <div class="modal-content" style="max-width: 700px; text-align: left; max-height: 85vh; overflow-y: auto;">
            <h2 style="text-align: center;">⭐ Избранные шаблоны меню</h2>
            <div id="favoritesList" style="margin: 15px 0;"></div>
            <div class="modal-buttons" style="margin-top: 20px;">
                <button class="btn btn-cancel" onclick="closeFavoritesModal()">❌ Закрыть</button>
            </div>
        </div>
    </div>

    <!-- Модалка: применить шаблон -->
    <div id="applyFavModal" class="modal-overlay">
        <div class="modal-content" style="max-width: 480px; text-align: left;">
            <h2 style="text-align: center;">📥 Применить шаблон</h2>
            <p style="margin: 10px 0;">Шаблон: <strong id="applyFavTitle">—</strong></p>
            <label style="display:block; margin: 10px 0;">
                <strong>Применить с даты</strong>
                <input type="date" id="applyFavDate"
                       style="width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px;">
            </label>
            <label style="display:block; margin: 10px 0;">
                <input type="checkbox" id="applyFavOverwrite"> Перезаписать существующие дни в диапазоне
            </label>
            <div class="modal-buttons" style="margin-top: 20px;">
                <button class="btn" onclick="doApplyFavorite()" style="background:#388e3c;">✅ Применить</button>
                <button class="btn btn-cancel" onclick="closeApplyFavModal()">❌ Отмена</button>
            </div>
        </div>
    </div>

    <!-- Модалка: добавление блюда -->
    <div id="addDishModal" class="modal-overlay">
        <div class="modal-content" style="max-width: 600px; text-align: left;">
            <h2 style="text-align: center;">🍳 Добавить блюдо</h2>
            <label style="display:block; margin-bottom: 10px;">
                <strong>Название блюда *</strong>
                <input type="text" id="newDishName" placeholder="Например: Борщ"
                       style="width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px; font-size: 15px;">
            </label>
            <label style="display:block; margin-bottom: 15px;">
                <strong>Категория</strong>
                <select id="newDishCategory"
                        style="width: 100%; padding: 10px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px; font-size: 15px;">
                    <option value="breakfast">Завтрак</option>
                    <option value="lunch">Обед</option>
                    <option value="dinner">Ужин</option>
                    <option value="snack">Перекус</option>
                </select>
            </label>
            <div style="margin-bottom: 10px;">
                <strong>Ингредиенты</strong>
                <p style="font-size:13px; color:#888; margin:4px 0 8px;">Начните вводить название — подставятся продукты из справочника.</p>
                <div id="ingredientsList" style="margin-top: 8px;"></div>
                <button type="button" class="btn btn-add" style="margin-top: 10px;"
                        onclick="addIngredientRow()">+ Добавить ингредиент</button>
            </div>
            <div class="modal-buttons" style="margin-top: 20px;">
                <button class="btn" id="dishSaveBtn" onclick="saveNewDish()" style="background:#388e3c;">✅ Сохранить блюдо</button>
                <button class="btn btn-cancel" onclick="closeAddDishModal()">❌ Отмена</button>
            </div>
        </div>
    </div>

    <!-- Модалка: справочник блюд -->
    <div id="dishesModal" class="modal-overlay">
        <div class="modal-content" style="max-width: 900px; text-align: left; max-height: 85vh; overflow-y: auto;">
            <h2 style="text-align: center;">📚 Справочник блюд</h2>
            <div style="margin: 15px 0;">
                <input type="text" id="dishSearchInput" placeholder="🔍 Поиск по названию..."
                       oninput="renderDishesList()"
                       style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 15px;">
            </div>
            <div style="margin: 10px 0;">
                <label>Категория:
                    <select id="dishCatFilter" onchange="renderDishesList()"
                            style="padding: 8px; border-radius: 4px;">
                        <option value="">Все</option>
                        <option value="breakfast">Завтрак</option>
                        <option value="lunch">Обед</option>
                        <option value="dinner">Ужин</option>
                        <option value="snack">Перекус</option>
                    </select>
                </label>
            </div>
            <div id="dishesListContainer"></div>
            <div class="modal-buttons" style="margin-top: 20px;">
                <button class="btn btn-cancel" onclick="closeDishesModal()">❌ Закрыть</button>
            </div>
        </div>
    </div>

    <!-- Модалка: справочник продуктов -->
    <div id="productsModal" class="modal-overlay">
        <div class="modal-content" style="max-width: 900px; text-align: left; max-height: 85vh; overflow-y: auto;">
            <h2 style="text-align: center;">🥕 Справочник продуктов</h2>
            <div style="margin: 15px 0; display:flex; gap:10px; flex-wrap:wrap;">
                <input type="text" id="productSearchInput" placeholder="🔍 Поиск по названию..."
                       oninput="renderProductsList()"
                       style="flex:1; min-width:200px; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 15px;">
                <label>Категория:
                    <select id="productCatFilter" onchange="renderProductsList()"
                            style="padding: 8px; border-radius: 4px;">
                        <option value="">Все</option>
                        <option value="Овощи">Овощи</option>
                        <option value="Фрукты">Фрукты</option>
                        <option value="Мясо">Мясо</option>
                        <option value="Рыба">Рыба</option>
                        <option value="Молочное">Молочное</option>
                        <option value="Крупы">Крупы</option>
                        <option value="Яйца">Яйца</option>
                        <option value="Прочее">Прочее</option>
                        <option value="Импорт">Импорт</option>
                    </select>
                </label>
                <button class="btn btn-add" onclick="showAddProductForm()">+ Добавить продукт</button>
            </div>
            <div id="productForm" style="display:none; background:#f0f7ff; padding:12px; border-radius:8px; margin-bottom:12px;">
                <strong id="productFormTitle">Новый продукт</strong>
                <div style="display:flex; gap:8px; margin-top:8px; flex-wrap:wrap;">
                    <input type="text" id="productFormName" placeholder="Название"
                           style="flex:2; min-width:180px; padding:8px; border:1px solid #ddd; border-radius:4px;">
                    <input type="text" id="productFormUnit" placeholder="Ед. (г/мл/шт)"
                           style="flex:1; min-width:100px; padding:8px; border:1px solid #ddd; border-radius:4px;">
                    <input type="text" id="productFormCategory" placeholder="Категория"
                           style="flex:1; min-width:120px; padding:8px; border:1px solid #ddd; border-radius:4px;">
                </div>
                <div style="margin-top:8px; display:flex; gap:8px;">
                    <button class="btn btn-add" onclick="saveProductForm()">💾 Сохранить</button>
                    <button class="btn btn-cancel" onclick="hideProductForm()">❌ Отмена</button>
                </div>
            </div>
            <div id="productsListContainer"></div>
            <div class="modal-buttons" style="margin-top: 20px;">
                <button class="btn btn-cancel" onclick="closeProductsModal()">❌ Закрыть</button>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/choices.js/public/assets/scripts/choices.min.js"></script>

    <script>
        let daysData = {};
        let dishesList = [];
        let productsList = [];
        let favoritesList = [];
        let shoppingList = [];
        let choicesInstances = [];
        let ingredientRowCounter = 0;
        let categoryFilter = '';
        let editingProductId = null;
        let editingShopId = null;
        let duplicateFromDate = '';
        let applyFavoriteId = null;

        // ============ ЗАГРУЗКА ДАННЫХ ============

        async function loadDishes() {
            try {
                const response = await fetch('/api/dishes');
                dishesList = await response.json();
            } catch (error) { console.error('Ошибка загрузки блюд:', error); }
        }

        async function loadProducts() {
            try {
                const response = await fetch('/api/products');
                productsList = await response.json();
                updateProductsDatalist();
            } catch (error) { console.error('Ошибка загрузки продуктов:', error); }
        }

        async function loadFavorites() {
            try {
                const response = await fetch('/api/favorites');
                favoritesList = await response.json();
            } catch (error) { console.error('Ошибка загрузки избранного:', error); }
        }

        async function loadShopping() {
            try {
                const response = await fetch('/api/shopping');
                shoppingList = await response.json();
            } catch (error) { console.error('Ошибка загрузки покупок:', error); }
        }

        function updateProductsDatalist() {
            const dl = document.getElementById('productsDatalist');
            if (!dl) return;
            dl.innerHTML = '';
            productsList.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.name;
                if (p.unit) opt.label = p.unit;
                dl.appendChild(opt);
            });
        }

        async function loadMenu() {
            try {
                const response = await fetch('/api/menu');
                const menu = await response.json();
                daysData = {};
                menu.forEach(item => {
                    if (!daysData[item.date]) daysData[item.date] = {};
                    daysData[item.date][item.meal_type + '_text']    = item.text || '';
                    daysData[item.date][item.meal_type + '_dish_id'] = item.dish_id || null;
                    // Сохраняем порции
                    daysData[item.date][item.meal_type + '_servings'] = item.servings || 1;
                });
                renderMenu();
            } catch (error) { console.error('Ошибка загрузки меню:', error); }
        }

        // ============ УТИЛИТЫ ============

        function dayNameRu(dateStr) {
            const d = new Date(dateStr + 'T00:00:00');
            const names = ['Воскресенье','Понедельник','Вторник','Среда','Четверг','Пятница','Суббота'];
            return names[d.getDay()];
        }

        function formatDateRu(dateStr) {
            const [y, m, d] = dateStr.split('-');
            return `${d}.${m}.${y}`;
        }

        // ============ ОТРИСОВКА МЕНЮ ============

        function renderDishSelect(selectedDishId, dateStr, mealType) {
            let filtered = dishesList;
            if (categoryFilter) {
                filtered = dishesList.filter(d => d.category === categoryFilter);
            } else {
                filtered = dishesList.filter(d => !d.category || d.category === mealType);
            }

            let options = '<option value="">— не выбрано —</option>';
            if (selectedDishId && !filtered.find(d => d.id === selectedDishId)) {
                const selectedDish = dishesList.find(d => d.id === selectedDishId);
                if (selectedDish) {
                    options += `<option value="${selectedDish.id}" selected>${selectedDish.name}</option>`;
                }
            }
            filtered.forEach(d => {
                const sel = (d.id === selectedDishId) ? 'selected' : '';
                options += `<option value="${d.id}" ${sel}>${d.name}</option>`;
            });

            return `
                <div class="dish-cell">
                    <select class="dish-select"
                            data-date="${dateStr}"
                            data-meal="${mealType}">${options}</select>
                    <button class="btn-clear-dish"
                            title="Очистить позицию"
                            onclick="clearMenuItem('${dateStr}', '${mealType}')">✕</button>
                </div>
            `;
        }

        // Функция для отрисовки поля ввода порций
        function renderServingsInput(dateStr, servings) {
            return `<input type="number" class="servings-input"
                           min="1" value="${servings}"
                           data-date="${dateStr}"
                           onchange="updateServings(this)">`;
        }

        function onCategoryFilter(value) {
            categoryFilter = value || '';
            renderMenu();
        }

        function renderMenu() {
            choicesInstances.forEach(c => c.destroy());
            choicesInstances = [];

            const tbody = document.getElementById('menuBody');
            tbody.innerHTML = '';
            const dates = Object.keys(daysData).sort();

            if (dates.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Нет дней. Выберите дату и нажмите "Добавить день".</td></tr>';
                return;
            }

            dates.forEach(dateStr => {
                const dayData = daysData[dateStr];
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${formatDateRu(dateStr)}</td>
                    <td>${dayNameRu(dateStr)}</td>
                    <td>${renderDishSelect(dayData.breakfast_dish_id, dateStr, 'breakfast')}</td>
                    <td>${renderDishSelect(dayData.lunch_dish_id,    dateStr, 'lunch')}</td>
                    <td>${renderDishSelect(dayData.dinner_dish_id,   dateStr, 'dinner')}</td>
                    <td>${renderDishSelect(dayData.snack_dish_id,    dateStr, 'snack')}</td>
                    <td>
                        <!-- Поля для порций для каждого приема пищи -->
                        <div style="display:flex; flex-direction:column; gap:4px; align-items:center;">
                            <div title="Завтрак">${renderServingsInput(dateStr + '|breakfast', dayData.breakfast_servings)}</div>
                            <div title="Обед">${renderServingsInput(dateStr + '|lunch', dayData.lunch_servings)}</div>
                            <div title="Ужин">${renderServingsInput(dateStr + '|dinner', dayData.dinner_servings)}</div>
                            <div title="Перекус">${renderServingsInput(dateStr + '|snack', dayData.snack_servings)}</div>
                        </div>
                    </td>
                    <td class="day-controls">
                        <button class="btn-dup-day" title="Дублировать день"
                                onclick="openDuplicateModal('${dateStr}')">📋</button>
                        <button class="btn btn-small btn-delete" onclick="deleteDay('${dateStr}')">✕</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });

            document.querySelectorAll('.dish-select').forEach(selectEl => {
                const choices = new Choices(selectEl, {
                    searchEnabled: true,
                    searchPlaceholderValue: '🔍 Поиск блюда...',
                    noResultsText: 'Ничего не найдено',
                    itemSelectText: '',
                    shouldSort: false,
                    position: 'auto',
                    placeholder: true,
                    placeholderValue: '— не выбрано —',
                });
                selectEl.addEventListener('change', function () {
                    const val = selectEl.value;
                    const dateStr = selectEl.dataset.date;
                    const mealType = selectEl.dataset.meal;
                    if (val === "") {
                        saveMenuItem(dateStr, mealType, "", null);
                    } else {
                        const dishId = parseInt(val);
                        const dish = dishesList.find(d => d.id === dishId);
                        saveMenuItem(dateStr, mealType, dish ? dish.name : "", dishId);
                    }
                });
                choicesInstances.push(choices);
            });
        }

        // ============ СОХРАНЕНИЕ ============

        async function saveMenuItem(dateStr, mealType, text, dishId = null) {
            // Получаем текущее значение порций, чтобы не сбросить его
            const currentServings = daysData[dateStr] ? (daysData[dateStr][mealType + '_servings'] || 1) : 1;
            try {
                await fetch('/api/menu', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        date: dateStr,
                        meal_type: mealType,
                        text: text,
                        dish_id: dishId,
                        servings: currentServings // Передаем порции
                    })
                });
                await loadMenu();
            } catch (error) { console.error('Ошибка сохранения:', error); }
        }

        // Новая функция для обновления порций
        async function updateServings(inputEl) {
            let val = parseInt(inputEl.value);
            if (isNaN(val) || val < 1) {
                val = 1;
                inputEl.value = 1;
            }
            const [dateStr, mealType] = inputEl.dataset.date.split('|');
            const text = daysData[dateStr] ? (daysData[dateStr][mealType + '_text'] || '') : '';
            const dishId = daysData[dateStr] ? (daysData[dateStr][mealType + '_dish_id'] || null) : null;

            // Обновляем локальные данные сразу, чтобы UI не "мигал"
            if (daysData[dateStr]) {
                daysData[dateStr][mealType + '_servings'] = val;
            }

            try {
                await fetch('/api/menu', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        date: dateStr,
                        meal_type: mealType,
                        text: text,
                        dish_id: dishId,
                        servings: val
                    })
                });
                // Мы не вызываем loadMenu() здесь, чтобы не перерисовывать всю таблицу
                // и не терять фокус с поля ввода.
            } catch (error) { console.error('Ошибка сохранения порций:', error); }
        }

        async function addDay() {
            const input = document.getElementById('newDayDate');
            const dateStr = input.value;
            if (!dateStr) { alert('Выберите дату'); return; }
            if (daysData[dateStr]) {
                alert('Этот день уже добавлен: ' + formatDateRu(dateStr));
                return;
            }
            try {
                await saveMenuItem(dateStr, 'breakfast', '', null);
                await saveMenuItem(dateStr, 'lunch',     '', null);
                await saveMenuItem(dateStr, 'dinner',    '', null);
                await saveMenuItem(dateStr, 'snack',     '', null);
                input.value = '';
                await loadMenu();
            } catch (error) { console.error('Ошибка добавления дня:', error); }
        }

        async function deleteDay(dateStr) {
            if (!confirm('Удалить день ' + formatDateRu(dateStr) + ' (' + dayNameRu(dateStr) + ')?')) return;
            try {
                await fetch(`/api/menu/day/${dateStr}`, { method: 'DELETE' });
                await loadMenu();
            } catch (error) { console.error('Ошибка удаления дня:', error); }
        }

        async function clearMenuItem(dateStr, mealType) {
            const mealNames = { breakfast: 'Завтрак', lunch: 'Обед', dinner: 'Ужин', snack: 'Перекус' };
            const mealName = mealNames[mealType] || mealType;
            if (!confirm(`Очистить «${mealName}» на ${formatDateRu(dateStr)}?`)) return;
            try { await saveMenuItem(dateStr, mealType, "", null); }
            catch (error) { console.error('Ошибка очистки позиции:', error); }
        }

        // ============ ФУНКЦИЯ 9: СЛУЧАЙНОЕ МЕНЮ ============

        function openRandomModal() {
            document.getElementById('randomStartDate').value = new Date().toISOString().slice(0, 10);
            document.getElementById('randomDays').value = 7;
            document.getElementById('randomModal').classList.add('active');
        }
        function closeRandomModal() {
            document.getElementById('randomModal').classList.remove('active');
        }
        async function doGenerateRandom() {
            const startDate = document.getElementById('randomStartDate').value;
            const days = parseInt(document.getElementById('randomDays').value) || 7;
            if (!startDate) { alert('Выберите дату начала'); return; }
            if (days < 1 || days > 30) { alert('Количество дней: 1–30'); return; }
            try {
                const resp = await fetch('/api/menu/random', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ start_date: startDate, days: days })
                });
                const data = await resp.json();
                if (!resp.ok) { alert('Ошибка: ' + (data.detail || 'не удалось сгенерировать')); return; }
                closeRandomModal();
                alert(data.message || 'Меню сгенерировано!');
                await loadMenu();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }

        // ============ ФУНКЦИЯ 10: ДУБЛИРОВАНИЕ ДНЯ ============

        function openDuplicateModal(fromDate) {
            duplicateFromDate = fromDate;
            document.getElementById('dupFromLabel').textContent = formatDateRu(fromDate);
            document.getElementById('dupToDate').value = '';
            document.getElementById('dupOverwrite').checked = false;
            document.getElementById('duplicateModal').classList.add('active');
        }
        function closeDuplicateModal() {
            document.getElementById('duplicateModal').classList.remove('active');
        }
        async function doDuplicateDay() {
            const toDate = document.getElementById('dupToDate').value;
            const overwrite = document.getElementById('dupOverwrite').checked;
            if (!toDate) { alert('Выберите целевую дату'); return; }
            if (toDate === duplicateFromDate) { alert('Исходная и целевая даты совпадают'); return; }
            try {
                const resp = await fetch('/api/menu/duplicate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ from_date: duplicateFromDate, to_date: toDate, overwrite: overwrite })
                });
                const data = await resp.json();
                if (!resp.ok) { alert('Ошибка: ' + (data.detail || 'не удалось скопировать')); return; }
                closeDuplicateModal();
                alert(data.message || 'День скопирован!');
                await loadMenu();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }

        // ============ ИЗБРАННОЕ ============

        function openSaveFavoriteModal() {
            const dates = Object.keys(daysData).sort();
            if (dates.length === 0) {
                alert('Меню пустое — нечего сохранять');
                return;
            }
            document.getElementById('favTitle').value = '';
            document.getElementById('favFromDate').value = dates[0];
            document.getElementById('favToDate').value = dates[dates.length - 1];
            document.getElementById('saveFavModal').classList.add('active');
        }
        function closeSaveFavoriteModal() {
            document.getElementById('saveFavModal').classList.remove('active');
        }
        async function doSaveFavorite() {
            const title = document.getElementById('favTitle').value.trim();
            const fromDate = document.getElementById('favFromDate').value;
            const toDate = document.getElementById('favToDate').value;
            if (!title) { alert('Введите название шаблона'); return; }
            if (!fromDate || !toDate) { alert('Укажите обе даты'); return; }
            if (fromDate > toDate) { alert('Дата "с" больше даты "по"'); return; }
            try {
                const resp = await fetch('/api/favorites', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ title, from_date: fromDate, to_date: toDate })
                });
                const data = await resp.json();
                if (!resp.ok) { alert('Ошибка: ' + (data.detail || 'не удалось сохранить')); return; }
                closeSaveFavoriteModal();
                alert('Шаблон сохранён в избранное!');
                await loadFavorites();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }

        async function openFavoritesModal() {
            await loadFavorites();
            renderFavoritesList();
            document.getElementById('favoritesModal').classList.add('active');
        }
        function closeFavoritesModal() {
            document.getElementById('favoritesModal').classList.remove('active');
        }
        function renderFavoritesList() {
            const container = document.getElementById('favoritesList');
            if (favoritesList.length === 0) {
                container.innerHTML = '<p class="empty-state">Избранных шаблонов пока нет.</p>';
                return;
            }
            let html = '';
            favoritesList.forEach(f => {
                const safeId = f.id;
                html += '<div class="fav-item">' +
                    '<div>' +
                        '<strong>' + escapeHtml(f.title) + '</strong>' +
                        '<small>' + formatDateRu(f.from_date) + ' — ' + formatDateRu(f.to_date) +
                                ' · ' + f.days_count + ' дн. · ' + f.created_at + '</small>' +
                    '</div>' +
                    '<div style="display:flex; gap:6px;">' +
                        '<button class="btn btn-small" onclick="openApplyFavModal(' + safeId + ', \'' +
                            escapeHtml(f.title).replace(/'/g, "\\'") + '\')" style="background:#388e3c;">📥 Применить</button>' +
                        '<button class="btn btn-small btn-delete" onclick="deleteFavorite(' + safeId + ', \'' +
                            escapeHtml(f.title).replace(/'/g, "\\'") + '\')">🗑️</button>' +
                    '</div>' +
                    '</div>';
            });
            container.innerHTML = html;
        }

        function escapeHtml(str) {
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }
        function openApplyFavModal(id, title) {
            applyFavoriteId = id;
            document.getElementById('applyFavTitle').textContent = title;
            document.getElementById('applyFavDate').value = new Date().toISOString().slice(0, 10);
            document.getElementById('applyFavOverwrite').checked = false;
            document.getElementById('applyFavModal').classList.add('active');
        }
        function closeApplyFavModal() {
            document.getElementById('applyFavModal').classList.remove('active');
        }
        async function doApplyFavorite() {
            const toDate = document.getElementById('applyFavDate').value;
            const overwrite = document.getElementById('applyFavOverwrite').checked;
            if (!toDate) { alert('Выберите дату'); return; }
            try {
                const resp = await fetch('/api/favorites/apply', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ favorite_id: applyFavoriteId, to_date: toDate, overwrite: overwrite })
                });
                const data = await resp.json();
                if (!resp.ok) { alert('Ошибка: ' + (data.detail || 'не удалось применить')); return; }
                closeApplyFavModal();
                closeFavoritesModal();
                alert(data.message || 'Шаблон применён!');
                await loadMenu();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }

        async function deleteFavorite(id, title) {
            if (!confirm(`Удалить шаблон «${title}»?`)) return;
            try {
                const resp = await fetch(`/api/favorites/${id}`, { method: 'DELETE' });
                if (!resp.ok) { alert('Не удалось удалить'); return; }
                await loadFavorites();
                renderFavoritesList();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }

        // ============ ФУНКЦИИ 5 и 6: СПИСОК ПОКУПОК ============

        async function openShoppingModal() {
            await loadShopping();
            renderShoppingList();
            hideShopForm();
            document.getElementById('shoppingModal').classList.add('active');
        }
        function closeShoppingModal() {
            document.getElementById('shoppingModal').classList.remove('active');
        }

        function renderShoppingList() {
            const container = document.getElementById('shoppingListContainer');
            if (shoppingList.length === 0) {
                container.innerHTML = '<p class="empty-state">Список покупок пуст. Нажмите «Сформировать из меню» или «Добавить позицию».</p>';
                return;
            }
            let html = '<table class="shop-table"><thead><tr>' +
                '<th style="width:24px;"></th>' +
                '<th>Наименование</th><th>Кол-во</th><th>Ед.</th>' +
                '<th style="width:140px;">Действия</th>' +
                '</tr></thead><tbody>';
            shoppingList.forEach(item => {
                const boughtCls = item.bought ? 'bought' : '';
                const safeName = escapeHtml(item.name || '').replace(/'/g, "\\'");
                html += `<tr class="${boughtCls}">
                    <td><input type="checkbox" class="shop-check" ${item.bought ? 'checked' : ''}
                               onchange="toggleShoppingBought(${item.id})"></td>
                    <td>${escapeHtml(item.name || '')}</td>
                    <td>${escapeHtml(item.quantity || '')}</td>
                    <td>${escapeHtml(item.unit || '')}</td>
                    <td>
                        <div class="shop-actions">
                            <button class="btn btn-small" onclick="editShoppingItem(${item.id})">✏️</button>
                            <button class="btn btn-small btn-delete" onclick="deleteShoppingItem(${item.id}, '${safeName}')">🗑️</button>
                        </div>
                    </td>
                </tr>`;
            });
            html += '</tbody></table>';
            container.innerHTML = html;
        }

        function showAddShoppingForm() {
            editingShopId = null;
            document.getElementById('shopFormTitle').textContent = 'Новая позиция';
            document.getElementById('shopFormName').value = '';
            document.getElementById('shopFormQty').value = '';
            document.getElementById('shopFormUnit').value = '';
            document.getElementById('shopFormCat').value = '';
            document.getElementById('shopForm').style.display = 'block';
        }
        function hideShopForm() {
            document.getElementById('shopForm').style.display = 'none';
            editingShopId = null;
        }

        async function saveShopForm() {
            const name = document.getElementById('shopFormName').value.trim();
            const quantity = document.getElementById('shopFormQty').value.trim();
            const unit = document.getElementById('shopFormUnit').value.trim();
            const category = document.getElementById('shopFormCat').value.trim();
            if (!name) { alert('Введите название'); return; }
            try {
                let resp;
                if (editingShopId) {
                    resp = await fetch(`/api/shopping/${editingShopId}`, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ name, quantity, unit, category })
                    });
                } else {
                    resp = await fetch('/api/shopping', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ name, quantity, unit, category })
                    });
                }
                const data = await resp.json();
                if (!resp.ok) { alert('Ошибка: ' + (data.detail || 'не удалось сохранить')); return; }
                hideShopForm();
                await loadShopping();
                renderShoppingList();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }

        function editShoppingItem(id) {
            const item = shoppingList.find(x => x.id === id);
            if (!item) return;
            editingShopId = id;
            document.getElementById('shopFormTitle').textContent = 'Редактировать позицию';
            document.getElementById('shopFormName').value = item.name || '';
            document.getElementById('shopFormQty').value = item.quantity || '';
            document.getElementById('shopFormUnit').value = item.unit || '';
            document.getElementById('shopFormCat').value = item.category || '';
            document.getElementById('shopForm').style.display = 'block';
        }

        async function toggleShoppingBought(id) {
            try {
                const resp = await fetch(`/api/shopping/${id}/toggle`, { method: 'PATCH' });
                if (!resp.ok) { alert('Не удалось изменить статус'); return; }
                await loadShopping();
                renderShoppingList();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }

        async function deleteShoppingItem(id, name) {
            if (!confirm(`Удалить «${name}» из списка покупок?`)) return;
            try {
                const resp = await fetch(`/api/shopping/${id}`, { method: 'DELETE' });
                if (!resp.ok) { alert('Не удалось удалить'); return; }
                await loadShopping();
                renderShoppingList();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }

        async function clearShoppingList() {
            if (!confirm('Очистить весь список покупок?')) return;
            try {
                const resp = await fetch('/api/shopping', { method: 'DELETE' });
                if (!resp.ok) { alert('Не удалось очистить'); return; }
                await loadShopping();
                renderShoppingList();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }

        async function generateShoppingFromMenu() {
            if (!confirm('Сформировать список покупок из текущего меню?\n\n' +
                         'ВНИМАНИЕ: текущий список будет перезаписан.')) return;
            try {
                const resp = await fetch('/api/shopping/generate', { method: 'POST' });
                const data = await resp.json();
                if (!resp.ok) { alert('Ошибка: ' + (data.detail || 'не удалось сформировать')); return; }
                await loadShopping();
                renderShoppingList();
                alert(data.message || 'Список сформирован!');
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }

        async function copyShoppingList() {
            const toBuy = shoppingList.filter(i => !i.bought);
            if (toBuy.length === 0) { alert('Нет позиций к покупке'); return; }
            const text = buildShoppingText(toBuy);
            try {
                await navigator.clipboard.writeText(text);
                alert('Список к покупке скопирован в буфер обмена!');
            } catch (err) {
                console.error(err);
                alert('Не удалось скопировать');
            }
        }

        function buildShoppingText(items) {
            let text = 'СПИСОК ПОКУПОК\n' + '='.repeat(30) + '\n';
            items.forEach((item, i) => {
                text += (i + 1) + '. ' + item.name;
                if (item.quantity) text += ' — ' + item.quantity;
                if (item.unit) text += ' ' + item.unit;
                text += '\n';
            });
            text += '='.repeat(30) + '\n';
            text += 'Сформировано: ' + new Date().toLocaleString('ru-RU');
            return text;
        }

        function downloadShoppingList() {
            const toBuy = shoppingList.filter(i => !i.bought);
            if (toBuy.length === 0) { alert('Нет позиций к покупке'); return; }
            const text = buildShoppingText(toBuy);
            const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'shopping-list-' + new Date().toISOString().slice(0, 10) + '.txt';
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        function downloadShoppingCSV() {
            if (shoppingList.length === 0) { alert('Список покупок пуст'); return; }

            const toBuy = shoppingList.filter(i => !i.bought);
            const bought = shoppingList.filter(i => i.bought);

            const rowsAll = [];
            rowsAll.push(['ВСЕ ПОЗИЦИИ (' + shoppingList.length + ')']);
            rowsAll.push(['№', 'Наименование', 'Количество', 'Ед.', 'Куплено']);
            shoppingList.forEach((item, i) => {
                rowsAll.push([
                    String(i + 1),
                    item.name || '',
                    item.quantity || '',
                    item.unit || '',
                    item.bought ? 'Да' : 'Нет'
                ]);
            });

            const rowsBuy = [];
            rowsBuy.push(['К ПОКУПКЕ (' + toBuy.length + ')']);
            if (toBuy.length === 0) {
                rowsBuy.push(['Все позиции отмечены как купленные.']);
            } else {
                rowsBuy.push(['№', 'Наименование', 'Количество', 'Ед.']);
                toBuy.forEach((item, i) => {
                    rowsBuy.push([
                        String(i + 1),
                        item.name || '',
                        item.quantity || '',
                        item.unit || ''
                    ]);
                });
            }

            const rowsBought = [];
            rowsBought.push(['УЖЕ КУПЛЕНО (' + bought.length + ')']);
            if (bought.length === 0) {
                rowsBought.push(['—']);
            } else {
                rowsBought.push(['№', 'Наименование', 'Количество', 'Ед.']);
                bought.forEach((item, i) => {
                    rowsBought.push([
                        String(i + 1),
                        item.name || '',
                        item.quantity || '',
                        item.unit || ''
                    ]);
                });
            }

            const maxRows = Math.max(rowsAll.length, rowsBuy.length, rowsBought.length);

            let csv = '\uFEFF'; // BOM для Excel

            csv += 'СПИСОК ПОКУПОК;Сформировано:;"' +
                   new Date().toLocaleString('ru-RU').replace(/"/g, '""') + '"\n\n';

            for (let r = 0; r < maxRows; r++) {
                const a = rowsAll[r]    ? rowsAll[r]    : [];
                const b = rowsBuy[r]    ? rowsBuy[r]    : [];
                const c = rowsBought[r] ? rowsBought[r] : [];

                const q = (val) => '"' + String(val == null ? '' : val).replace(/"/g, '""') + '"';

                const partA = [0, 1, 2, 3, 4].map(i => q(a[i] != null ? a[i] : ''));
                const partB = [0, 1, 2, 3].map(i => q(b[i] != null ? b[i] : ''));
                const partC = [0, 1, 2, 3].map(i => q(c[i] != null ? c[i] : ''));

                csv += partA.join(';') + ';" "' + ';' +
                       partB.join(';') + ';" "' + ';' +
                       partC.join(';') + '\n';
            }

            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'shopping-list-' + new Date().toISOString().slice(0, 10) + '.csv';
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        function printShoppingList() {
            if (shoppingList.length === 0) { alert('Список покупок пуст'); return; }

            const toBuy = shoppingList.filter(i => !i.bought);
            const bought = shoppingList.filter(i => i.bought);

            let printHTML = '<html><head><meta charset="UTF-8"><title>Список покупок</title>';
            printHTML += '<style>' +
                '@page { size: A4 landscape; margin: 10mm; }' +
                'body{font-family:Arial,sans-serif;padding:10px;line-height:1.25;font-size:11px;}' +
                'h1{text-align:center;margin:0 0 4px 0;font-size:20px;}' +
                '.subtitle{text-align:center;color:#666;margin-bottom:14px;font-size:11px;}' +
                '.tables-row{display:table;width:100%;table-layout:fixed;border-collapse:separate;border-spacing:0;}' +
                '.table-block{display:table-cell;vertical-align:top;padding:0 6px;}' +
                '.table-block.col-all    {width:40%;}' +
                '.table-block.col-buy    {width:36%;}' +
                '.table-block.col-bought {width:24%;}' +
                '.table-block h2{margin:0 0 4px 0;font-size:12px;border-bottom:2px solid #000;padding-bottom:2px;}' +
                'table{width:100%;border-collapse:collapse;margin-bottom:8px;font-size:11px;table-layout:fixed;}' +
                'th,td{border:1px solid #000;padding:2px 4px;text-align:left;' +
                     'overflow:hidden;text-overflow:ellipsis;word-wrap:break-word;vertical-align:top;}' +
                'th{background:#eee;font-weight:bold;}' +
                '.col-num  {width:24px;text-align:right;}' +
                '.col-qty  {width:56px;text-align:right;white-space:nowrap;}' +
                '.col-unit {width:36px;text-align:left;white-space:nowrap;}' +
                '.col-bought{width:56px;text-align:center;white-space:nowrap;}' +
                '.bought td{text-decoration:line-through;color:#888;}' +
                '.empty{color:#888;font-style:italic;padding:6px 0;font-size:11px;}' +
                '@media print{' +
                    'body{padding:0;}' +
                    '.no-print{display:none;}' +
                '}' +
                '</style>';
            printHTML += '</head><body>';
            printHTML += '<h1>🛒 Список покупок</h1>';
            printHTML += '<div class="subtitle">Сформировано: ' +
                         new Date().toLocaleString('ru-RU') + '</div>';

            printHTML += '<div class="tables-row">';

            printHTML += '<div class="table-block col-all">';
            printHTML += '<h2>Все позиции (' + shoppingList.length + ')</h2>';
            printHTML += '<table><colgroup>' +
                '<col class="col-num"><col><col class="col-qty">' +
                '<col class="col-unit"><col class="col-bought">' +
                '</colgroup><thead><tr>' +
                '<th class="col-num">№</th>' +
                '<th>Наименование</th>' +
                '<th class="col-qty">Кол-во</th>' +
                '<th class="col-unit">Ед.</th>' +
                '<th class="col-bought">Куплено</th>' +
                '</tr></thead><tbody>';
            shoppingList.forEach((item, i) => {
                const cls = item.bought ? ' class="bought"' : '';
                printHTML += `<tr${cls}>` +
                    `<td class="col-num">${i + 1}</td>` +
                    `<td>${escapeHtml(item.name || '')}</td>` +
                    `<td class="col-qty">${escapeHtml(item.quantity || '')}</td>` +
                    `<td class="col-unit">${escapeHtml(item.unit || '')}</td>` +
                    `<td class="col-bought">${item.bought ? 'Да' : 'Нет'}</td>` +
                    `</tr>`;
            });
            printHTML += '</tbody></table></div>';

            printHTML += '<div class="table-block col-buy">';
            printHTML += '<h2>СВОДНЫЙ СПИСОК — К ПОКУПКЕ (' + toBuy.length + ')</h2>';
            if (toBuy.length === 0) {
                printHTML += '<div class="empty">Все позиции отмечены как купленные.</div>';
            } else {
                printHTML += '<table><colgroup>' +
                    '<col class="col-num"><col><col class="col-qty"><col class="col-unit">' +
                    '</colgroup><thead><tr>' +
                    '<th class="col-num">№</th>' +
                    '<th>Наименование</th>' +
                    '<th class="col-qty">Кол-во</th>' +
                    '<th class="col-unit">Ед.</th>' +
                    '</tr></thead><tbody>';
                toBuy.forEach((item, i) => {
                    printHTML += '<tr>' +
                        `<td class="col-num">${i + 1}</td>` +
                        `<td>${escapeHtml(item.name || '')}</td>` +
                        `<td class="col-qty">${escapeHtml(item.quantity || '')}</td>` +
                        `<td class="col-unit">${escapeHtml(item.unit || '')}</td>` +
                        '</tr>';
                });
                printHTML += '</tbody></table>';
            }
            printHTML += '</div>';

            printHTML += '<div class="table-block col-bought">';
            printHTML += '<h2>Уже куплено (' + bought.length + ')</h2>';
            if (bought.length === 0) {
                printHTML += '<div class="empty">—</div>';
            } else {
                printHTML += '<table><colgroup>' +
                    '<col class="col-num"><col><col class="col-qty"><col class="col-unit">' +
                    '</colgroup><thead><tr>' +
                    '<th class="col-num">№</th>' +
                    '<th>Наименование</th>' +
                    '<th class="col-qty">Кол-во</th>' +
                    '<th class="col-unit">Ед.</th>' +
                    '</tr></thead><tbody>';
                bought.forEach((item, i) => {
                    printHTML += '<tr class="bought">' +
                        `<td class="col-num">${i + 1}</td>` +
                        `<td>${escapeHtml(item.name || '')}</td>` +
                        `<td class="col-qty">${escapeHtml(item.quantity || '')}</td>` +
                        `<td class="col-unit">${escapeHtml(item.unit || '')}</td>` +
                        '</tr>';
                });
                printHTML += '</tbody></table>';
            }
            printHTML += '</div>';

            printHTML += '</div>'; // .tables-row
            printHTML += '</body></html>';
            const w = window.open('', '_blank');
            w.document.write(printHTML);
            w.document.close();
            w.focus();
            setTimeout(() => { w.print(); w.close(); }, 300);
        }
        // ============ ОЧИСТКА ============

        async function clearAll() {
            if (!confirm('ВНИМАНИЕ: Это удалит все данные меню. Продолжить?')) return;
            try {
                await fetch('/api/clear', { method: 'POST' });
                await loadMenu();
            } catch (error) { console.error('Ошибка очистки:', error); }
        }

        // ============ ТЕМА ============

        function toggleTheme() {
            document.body.classList.toggle('dark-mode');
            localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
        }
        function initTheme() {
            const saved = localStorage.getItem('theme');
            if (saved === 'dark') document.body.classList.add('dark-mode');
        }

        // ============ ФОРМА ДОБАВЛЕНИЯ БЛЮДА ============

        function openAddDishModal() {
            document.getElementById('newDishName').value = '';
            document.getElementById('newDishCategory').value = 'breakfast';
            document.getElementById('ingredientsList').innerHTML = '';
            ingredientRowCounter = 0;
            const saveBtn = document.getElementById('dishSaveBtn');
            saveBtn.textContent = '✅ Сохранить блюдо';
            saveBtn.setAttribute('onclick', 'saveNewDish()');
            addIngredientRow(); addIngredientRow(); addIngredientRow();
            document.getElementById('addDishModal').classList.add('active');
        }
        function closeAddDishModal() {
            document.getElementById('addDishModal').classList.remove('active');
        }
        function addIngredientRow(name, qty, unit) {
            ingredientRowCounter++;
            const rowId = 'ing-row-' + ingredientRowCounter;
            const container = document.getElementById('ingredientsList');
            const row = document.createElement('div');
            row.className = 'ingredient-row';
            row.id = rowId;
            const safeName = (name || '').replace(/"/g, '&quot;');
            const safeQty  = (qty  || '').replace(/"/g, '&quot;');
            const safeUnit = (unit || '').replace(/"/g, '&quot;');
            row.innerHTML = `
                <input type="text" class="ing-name" list="productsDatalist"
                       placeholder="Название (из справочника)" value="${safeName}">
                <input type="text" class="ing-qty"  placeholder="Кол-во" value="${safeQty}">
                <input type="text" class="ing-unit" placeholder="Ед." value="${safeUnit}">
                <button type="button" onclick="removeIngredientRow('${rowId}')">✕</button>
            `;
            container.appendChild(row);
        }
        function removeIngredientRow(rowId) {
            const row = document.getElementById(rowId);
            if (row) row.remove();
        }
        async function saveNewDish() {
            const name = document.getElementById('newDishName').value.trim();
            const category = document.getElementById('newDishCategory').value;
            if (!name) { alert('Введите название блюда'); return; }
            const rows = document.querySelectorAll('#ingredientsList .ingredient-row');
            const ingredients = [];
            rows.forEach(row => {
                const ingName = row.querySelector('.ing-name').value.trim();
                const ingQty  = row.querySelector('.ing-qty').value.trim();
                const ingUnit = row.querySelector('.ing-unit').value.trim();
                if (ingName) ingredients.push({ name: ingName, quantity: ingQty, unit: ingUnit });
            });
            try {
                const response = await fetch('/api/dishes', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ name, category, ingredients })
                });
                if (!response.ok) {
                    const err = await response.json();
                    alert('Ошибка: ' + (err.detail || 'не удалось сохранить блюдо'));
                    return;
                }
                closeAddDishModal();
                alert('Блюдо "' + name + '" добавлено!');
                await loadDishes(); await loadProducts(); await loadMenu();
            } catch (error) {
                console.error('Ошибка добавления блюда:', error);
                alert('Ошибка сети');
            }
        }

        // ============ СПРАВОЧНИК БЛЮД ============

        function openDishesModal() {
            document.getElementById('dishSearchInput').value = '';
            document.getElementById('dishCatFilter').value = '';
            renderDishesList();
            document.getElementById('dishesModal').classList.add('active');
        }
        function closeDishesModal() {
            document.getElementById('dishesModal').classList.remove('active');
        }
        function renderDishesList() {
            const container = document.getElementById('dishesListContainer');
            const searchText = (document.getElementById('dishSearchInput').value || '').trim().toLowerCase();
            const catFilter = document.getElementById('dishCatFilter').value;
            let filtered = dishesList;
            if (searchText) filtered = filtered.filter(d => d.name.toLowerCase().includes(searchText));
            if (catFilter) filtered = filtered.filter(d => d.category === catFilter);
            if (filtered.length === 0) {
                container.innerHTML = '<p class="empty-state">Ничего не найдено.</p>';
                return;
            }
            const catNames = { breakfast: 'Завтрак', lunch: 'Обед', dinner: 'Ужин', snack: 'Перекус' };
            let html = '<table class="menu-table" style="margin:0;"><thead><tr><th>Название</th><th>Категория</th><th>Действия</th></tr></thead><tbody>';
            filtered.forEach(d => {
                const safeName = d.name.replace(/'/g, "\\'");
                html += `<tr>
                    <td style="text-align:left;">${d.name}</td>
                    <td>${catNames[d.category] || d.category || '—'}</td>
                    <td>
                        <button class="btn btn-small" onclick="editDish(${d.id})">✏️</button>
                        <button class="btn btn-small btn-delete" onclick="deleteDish(${d.id}, '${safeName}')">🗑️</button>
                    </td>
                </tr>`;
            });
            html += '</tbody></table>';
            container.innerHTML = html;
        }
        async function deleteDish(dishId, dishName) {
            if (!confirm(`Удалить блюдо «${dishName}»? Все ингредиенты тоже удалятся.`)) return;
            try {
                const resp = await fetch(`/api/dishes/${dishId}`, { method: 'DELETE' });
                if (!resp.ok) { alert('Не удалось удалить блюдо'); return; }
                await loadDishes(); renderDishesList(); await loadMenu();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }
        async function editDish(dishId) {
            try {
                const resp = await fetch(`/api/dishes/${dishId}/ingredients`);
                const ingredients = await resp.json();
                const dish = dishesList.find(d => d.id === dishId);
                if (!dish) return;
                document.getElementById('newDishName').value = dish.name;
                document.getElementById('newDishCategory').value = dish.category || 'breakfast';
                const list = document.getElementById('ingredientsList');
                list.innerHTML = '';
                ingredientRowCounter = 0;
                if (ingredients.length === 0) { addIngredientRow(); }
                else { ingredients.forEach(ing => addIngredientRow(ing.name, ing.quantity, ing.unit)); }
                const saveBtn = document.getElementById('dishSaveBtn');
                saveBtn.textContent = '💾 Обновить блюдо';
                saveBtn.setAttribute('onclick', `updateDish(${dishId})`);
                closeDishesModal();
                document.getElementById('addDishModal').classList.add('active');
            } catch (err) { console.error(err); alert('Не удалось загрузить ингредиенты'); }
        }
        async function updateDish(dishId) {
            const name = document.getElementById('newDishName').value.trim();
            const category = document.getElementById('newDishCategory').value;
            if (!name) { alert('Введите название блюда'); return; }
            const rows = document.querySelectorAll('#ingredientsList .ingredient-row');
            const ingredients = [];
            rows.forEach(row => {
                const ingName = row.querySelector('.ing-name').value.trim();
                const ingQty  = row.querySelector('.ing-qty').value.trim();
                const ingUnit = row.querySelector('.ing-unit').value.trim();
                if (ingName) ingredients.push({ name: ingName, quantity: ingQty, unit: ingUnit });
            });
            try {
                const resp = await fetch(`/api/dishes/${dishId}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ name, category, ingredients })
                });
                if (!resp.ok) {
                    const err = await resp.json();
                    alert('Ошибка: ' + (err.detail || 'не удалось обновить'));
                    return;
                }
                closeAddDishModal();
                alert(`Блюдо "${name}" обновлено!`);
                await loadDishes(); await loadProducts(); await loadMenu();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }

        // ============ СПРАВОЧНИК ПРОДУКТОВ ============

        function openProductsModal() {
            document.getElementById('productSearchInput').value = '';
            document.getElementById('productCatFilter').value = '';
            hideProductForm();
            renderProductsList();
            document.getElementById('productsModal').classList.add('active');
        }
        function closeProductsModal() {
            document.getElementById('productsModal').classList.remove('active');
        }
        function renderProductsList() {
            const container = document.getElementById('productsListContainer');
            const searchText = (document.getElementById('productSearchInput').value || '').trim().toLowerCase();
            const catFilter = document.getElementById('productCatFilter').value;
            let filtered = productsList;
            if (searchText) filtered = filtered.filter(p => p.name.toLowerCase().includes(searchText));
            if (catFilter) filtered = filtered.filter(p => p.category === catFilter);
            if (filtered.length === 0) {
                container.innerHTML = '<p class="empty-state">Ничего не найдено.</p>';
                return;
            }
            let html = '<table class="menu-table" style="margin:0;"><thead><tr><th>Наименование</th><th>Ед.</th><th>Категория</th><th>Действия</th></tr></thead><tbody>';
            filtered.forEach(p => {
                const safeName = p.name.replace(/'/g, "\\'");
                html += `<tr>
                    <td style="text-align:left;">${p.name}</td>
                    <td>${p.unit || '—'}</td>
                    <td>${p.category || '—'}</td>
                    <td>
                        <button class="btn btn-small" onclick="editProduct(${p.id})">✏️</button>
                        <button class="btn btn-small btn-delete" onclick="deleteProduct(${p.id}, '${safeName}')">🗑️</button>
                    </td>
                </tr>`;
            });
            html += '</tbody></table>';
            container.innerHTML = html;
        }
        function showAddProductForm() {
            editingProductId = null;
            document.getElementById('productFormTitle').textContent = 'Новый продукт';
            document.getElementById('productFormName').value = '';
            document.getElementById('productFormUnit').value = '';
            document.getElementById('productFormCategory').value = '';
            document.getElementById('productForm').style.display = 'block';
        }
        function hideProductForm() {
            document.getElementById('productForm').style.display = 'none';
            editingProductId = null;
        }
        function editProduct(productId) {
            const p = productsList.find(x => x.id === productId);
            if (!p) return;
            editingProductId = productId;
            document.getElementById('productFormTitle').textContent = 'Редактировать продукт';
            document.getElementById('productFormName').value = p.name;
            document.getElementById('productFormUnit').value = p.unit || '';
            document.getElementById('productFormCategory').value = p.category || '';
            document.getElementById('productForm').style.display = 'block';
        }
        async function saveProductForm() {
            const name = document.getElementById('productFormName').value.trim();
            const unit = document.getElementById('productFormUnit').value.trim();
            const category = document.getElementById('productFormCategory').value.trim();
            if (!name) { alert('Введите название продукта'); return; }
            try {
                let resp;
                if (editingProductId) {
                    resp = await fetch(`/api/products/${editingProductId}`, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ name, unit, category })
                    });
                } else {
                    resp = await fetch('/api/products', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ name, unit, category })
                    });
                }
                if (!resp.ok) {
                    const err = await resp.json();
                    alert('Ошибка: ' + (err.detail || 'не удалось сохранить продукт'));
                    return;
                }
                hideProductForm();
                await loadProducts();
                renderProductsList();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }
        async function deleteProduct(productId, productName) {
            if (!confirm(`Удалить продукт «${productName}»?`)) return;
            try {
                const resp = await fetch(`/api/products/${productId}`, { method: 'DELETE' });
                if (!resp.ok) { alert('Не удалось удалить продукт'); return; }
                await loadProducts();
                renderProductsList();
            } catch (err) { console.error(err); alert('Ошибка сети'); }
        }

        // ============ ЗАКРЫТИЕ МОДАЛОК ПО ФОНУ ============

        document.addEventListener('click', function(e) {
            const ids = ['addDishModal','dishesModal','productsModal',
                         'randomModal','duplicateModal','saveFavModal','favoritesModal',
                         'applyFavModal','shoppingModal'];
            ids.forEach(id => {
                const m = document.getElementById(id);
                if (e.target === m) m.classList.remove('active');
            });
        });

        // ============ ЗАПУСК ============

        async function loadData() {
            await loadProducts();
            await loadDishes();
            await loadFavorites();
            await loadShopping();
            await loadMenu();
        }

        document.addEventListener('DOMContentLoaded', function() {
            initTheme();
            loadData();
        });
    </script>
</body>
</html>'''
    return HTMLResponse(content=html)


# ==================== API: МЕНЮ ====================

@app.get("/api/menu")
async def get_menu():
    db = SessionLocal()
    try:
        items = db.query(Menu).order_by(Menu.date).all()
        return [{"id": i.id, "date": i.date, "meal_type": i.meal_type,
                 "text": i.text, "dish_id": i.dish_id, "servings": i.servings or 1} for i in items]
    finally:
        db.close()


@app.post("/api/menu")
async def create_menu(item: MenuItemCreate):
    db = SessionLocal()
    try:
        existing = db.query(Menu).filter(
            Menu.date == item.date,
            Menu.meal_type == item.meal_type
        ).first()

        if existing:
            existing.text = item.text
            existing.dish_id = item.dish_id
            existing.servings = item.servings # Обновляем порции
            db.commit()
            db.refresh(existing)
            return {"id": existing.id, "date": existing.date, "meal_type": existing.meal_type,
                    "text": existing.text, "dish_id": existing.dish_id, "servings": existing.servings}

        db_item = Menu(date=item.date, meal_type=item.meal_type,
                       text=item.text, dish_id=item.dish_id, servings=item.servings)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return {"id": db_item.id, "date": db_item.date, "meal_type": db_item.meal_type,
                "text": db_item.text, "dish_id": db_item.dish_id, "servings": db_item.servings}
    finally:
        db.close()


@app.delete("/api/menu/day/{date_str}")
async def delete_day(date_str: str):
    db = SessionLocal()
    try:
        db.query(Menu).filter(Menu.date == date_str).delete()
        db.commit()
        return {"message": "День удален"}
    finally:
        db.close()


# ==================== API: СЛУЧАЙНОЕ МЕНЮ ====================

@app.post("/api/menu/random")
async def generate_random_menu(req: RandomMenuRequest):
    db = SessionLocal()
    try:
        try:
            start = date_cls.fromisoformat(req.start_date)
        except Exception:
            raise HTTPException(400, "Неверный формат даты (нужно YYYY-MM-DD)")

        days = req.days if 1 <= req.days <= 30 else 7

        dishes = db.query(Dish).all()
        by_cat = {"breakfast": [], "lunch": [], "dinner": [], "snack": []}
        for d in dishes:
            if d.category in by_cat:
                by_cat[d.category].append(d)

        for meal in ["breakfast", "lunch", "dinner", "snack"]:
            if not by_cat[meal]:
                raise HTTPException(400, f"Нет блюд для категории «{meal}». "
                                         f"Добавьте блюда в справочник.")

        created = 0
        for i in range(days):
            current = (start + timedelta(days=i)).isoformat()
            used_today = set()
            for meal in ["breakfast", "lunch", "dinner", "snack"]:
                candidates = [d for d in by_cat[meal] if d.id not in used_today]
                if not candidates:
                    candidates = by_cat[meal]
                dish = random.choice(candidates)
                used_today.add(dish.id)

                existing = db.query(Menu).filter(
                    Menu.date == current,
                    Menu.meal_type == meal
                ).first()

                # При генерации ставим 1 порцию по умолчанию
                if existing:
                    existing.text = dish.name
                    existing.dish_id = dish.id
                    existing.servings = 1
                else:
                    db.add(Menu(date=current, meal_type=meal,
                                text=dish.name, dish_id=dish.id, servings=1))
                created += 1

        db.commit()
        return {"message": f"Сгенерировано {created} записей на {days} дн."}
    finally:
        db.close()


# ==================== API: ДУБЛИРОВАНИЕ ДНЯ ====================

@app.post("/api/menu/duplicate")
async def duplicate_menu(req: DuplicateMenuRequest):
    db = SessionLocal()
    try:
        if not req.from_date or not req.to_date:
            raise HTTPException(400, "Нужно указать обе даты")

        if req.from_date == req.to_date:
            raise HTTPException(400, "Исходная и целевая даты совпадают")

        source = db.query(Menu).filter(Menu.date == req.from_date).all()
        if not source:
            raise HTTPException(404, f"На {req.from_date} нет записей")

        target = db.query(Menu).filter(Menu.date == req.to_date).all()
        if target and not req.overwrite:
            raise HTTPException(
                400,
                f"На {req.to_date} уже есть записи. "
                f"Поставьте галочку «Перезаписать», чтобы заменить"
            )

        if target:
            db.query(Menu).filter(Menu.date == req.to_date).delete()

        for m in source:
            db.add(Menu(date=req.to_date, meal_type=m.meal_type,
                        text=m.text, dish_id=m.dish_id, servings=m.servings)) # Копируем порции
        db.commit()
        return {"message": f"Скопировано {len(source)} записей с "
                           f"{req.from_date} на {req.to_date}"}
    finally:
        db.close()


# ==================== API: ИЗБРАННОЕ ====================

@app.get("/api/favorites")
async def get_favorites():
    db = SessionLocal()
    try:
        items = db.query(Favorite).order_by(Favorite.id.desc()).all()
        result = []
        for f in items:
            try:
                data = json.loads(f.data or "[]")
            except Exception:
                data = []
            offsets = {item.get("offset", 0) for item in data}
            result.append({
                "id": f.id,
                "title": f.title,
                "from_date": f.from_date,
                "to_date": f.to_date,
                "created_at": f.created_at,
                "days_count": len(offsets)
            })
        return result
    finally:
        db.close()


@app.post("/api/favorites")
async def save_favorite(req: SaveFavoriteRequest):
    db = SessionLocal()
    try:
        if not req.title.strip():
            raise HTTPException(400, "Введите название шаблона")

        try:
            start = date_cls.fromisoformat(req.from_date)
            end = date_cls.fromisoformat(req.to_date)
        except Exception:
            raise HTTPException(400, "Неверный формат даты")

        if end < start:
            raise HTTPException(400, "Дата 'по' раньше даты 'с'")

        records = db.query(Menu).filter(
            Menu.date >= req.from_date,
            Menu.date <= req.to_date
        ).all()

        if not records:
            raise HTTPException(404, "В указанном диапазоне нет записей меню")

        items_data = []
        for m in records:
            try:
                m_date = date_cls.fromisoformat(m.date)
                offset = (m_date - start).days
            except Exception:
                continue
            items_data.append({
                "offset": offset,
                "meal_type": m.meal_type,
                "text": m.text,
                "dish_id": m.dish_id,
                "servings": m.servings # Сохраняем порции в шаблон
            })

        fav = Favorite(
            title=req.title.strip(),
            from_date=req.from_date,
            to_date=req.to_date,
            created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
            data=json.dumps(items_data, ensure_ascii=False)
        )
        db.add(fav)
        db.commit()
        db.refresh(fav)
        return {"id": fav.id, "title": fav.title}
    finally:
        db.close()


@app.delete("/api/favorites/{fav_id}")
async def delete_favorite(fav_id: int):
    db = SessionLocal()
    try:
        fav = db.query(Favorite).filter(Favorite.id == fav_id).first()
        if not fav:
            raise HTTPException(404, "Шаблон не найден")
        db.delete(fav)
        db.commit()
        return {"message": "Шаблон удалён"}
    finally:
        db.close()


@app.post("/api/favorites/apply")
async def apply_favorite(req: ApplyFavoriteRequest):
    db = SessionLocal()
    try:
        fav = db.query(Favorite).filter(Favorite.id == req.favorite_id).first()
        if not fav:
            raise HTTPException(404, "Шаблон не найден")

        try:
            start = date_cls.fromisoformat(req.to_date)
        except Exception:
            raise HTTPException(400, "Неверный формат целевой даты")

        items = json.loads(fav.data or "[]")
        if not items:
            raise HTTPException(400, "Шаблон пуст")

        offsets = [item.get("offset", 0) for item in items]
        max_offset = max(offsets) if offsets else 0

        affected_dates = [(start + timedelta(days=o)).isoformat() for o in range(max_offset + 1)]
        existing = db.query(Menu).filter(Menu.date.in_(affected_dates)).count()

        if existing > 0 and not req.overwrite:
            raise HTTPException(
                400,
                f"В диапазоне {affected_dates[0]} — {affected_dates[-1]} уже есть записи. "
                f"Поставьте галочку «Перезаписать»"
            )

        if existing > 0 and req.overwrite:
            db.query(Menu).filter(Menu.date.in_(affected_dates)).delete()

        created = 0
        for item in items:
            offset = item.get("offset", 0)
            target_date = (start + timedelta(days=offset)).isoformat()
            db.add(Menu(
                date=target_date,
                meal_type=item.get("meal_type", ""),
                text=item.get("text", ""),
                dish_id=item.get("dish_id"),
                servings=item.get("servings", 1) # Восстанавливаем порции
            ))
            created += 1

        db.commit()
        return {"message": f"Применено {created} записей с {req.to_date}"}
    finally:
        db.close()


# ==================== API: СПРАВОЧНИК БЛЮД ====================

@app.get("/api/dishes")
async def get_dishes():
    db = SessionLocal()
    try:
        items = db.query(Dish).order_by(Dish.category, Dish.name).all()
        return [{"id": d.id, "name": d.name, "category": d.category} for d in items]
    finally:
        db.close()


@app.get("/api/dishes/{dish_id}/ingredients")
async def get_dish_ingredients(dish_id: int):
    db = SessionLocal()
    try:
        items = db.query(Ingredient).filter(Ingredient.dish_id == dish_id).all()
        return [{"id": i.id, "name": i.name, "quantity": i.quantity, "unit": i.unit} for i in items]
    finally:
        db.close()


@app.post("/api/dishes")
async def create_dish(item: DishCreate):
    db = SessionLocal()
    try:
        existing = db.query(Dish).filter(Dish.name.ilike(item.name.strip())).first()
        if existing:
            raise HTTPException(400, f"Блюдо '{item.name}' уже существует в справочнике")

        db_item = Dish(name=item.name.strip(), category=item.category.strip())
        db.add(db_item)
        db.commit()
        db.refresh(db_item)

        for ing in item.ingredients:
            ing_name = (ing.name or "").strip()
            ing_qty  = (ing.quantity or "").strip()
            ing_unit = (ing.unit or "").strip()
            if ing_name:
                db.execute(text(
                    "INSERT INTO ingredients (dish_id, name, quantity, unit) "
                    "VALUES (:d, :n, :q, :u)"
                ), {"d": db_item.id, "n": ing_name, "q": ing_qty, "u": ing_unit})
                _ensure_product(db, ing_name, ing_unit)
        db.commit()
        return {"id": db_item.id, "name": db_item.name, "category": db_item.category}
    finally:
        db.close()


@app.put("/api/dishes/{dish_id}")
async def update_dish(dish_id: int, item: DishCreate):
    db = SessionLocal()
    try:
        db_item = db.query(Dish).filter(Dish.id == dish_id).first()
        if not db_item:
            raise HTTPException(404, "Блюдо не найдено")

        existing = db.query(Dish).filter(
            Dish.name.ilike(item.name.strip()),
            Dish.id != dish_id
        ).first()
        if existing:
            raise HTTPException(400, f"Блюдо '{item.name}' уже существует")

        db_item.name = item.name.strip()
        db_item.category = item.category.strip()

        db.query(Ingredient).filter(Ingredient.dish_id == dish_id).delete()
        for ing in item.ingredients:
            ing_name = (ing.name or "").strip()
            ing_qty  = (ing.quantity or "").strip()
            ing_unit = (ing.unit or "").strip()
            if ing_name:
                db.execute(text(
                    "INSERT INTO ingredients (dish_id, name, quantity, unit) "
                    "VALUES (:d, :n, :q, :u)"
                ), {"d": dish_id, "n": ing_name, "q": ing_qty, "u": ing_unit})
                _ensure_product(db, ing_name, ing_unit)

        db.commit()
        return {"id": db_item.id, "name": db_item.name, "category": db_item.category}
    finally:
        db.close()


@app.delete("/api/dishes/{dish_id}")
async def delete_dish(dish_id: int):
    db = SessionLocal()
    try:
        db.query(Ingredient).filter(Ingredient.dish_id == dish_id).delete()
        db.query(Dish).filter(Dish.id == dish_id).delete()
        db.commit()
        return {"message": "Блюдо и ингредиенты удалены"}
    finally:
        db.close()


# ==================== ХЕЛПЕР ====================

def _ensure_product(db, name, unit=""):
    if not name:
        return
    existing = db.query(Product).filter(Product.name.ilike(name.strip())).first()
    if existing:
        return
    db.add(Product(name=name.strip(), unit=(unit or "").strip(), category="Импорт"))


# ==================== API: СПРАВОЧНИК ПРОДУКТОВ ====================

@app.get("/api/products")
async def get_products():
    db = SessionLocal()
    try:
        items = db.query(Product).order_by(Product.category, Product.name).all()
        return [{"id": p.id, "name": p.name, "unit": p.unit, "category": p.category} for p in items]
    finally:
        db.close()


@app.post("/api/products")
async def create_product(item: ProductCreate):
    db = SessionLocal()
    try:
        if not item.name.strip():
            raise HTTPException(400, "Название продукта не может быть пустым")
        existing = db.query(Product).filter(Product.name.ilike(item.name.strip())).first()
        if existing:
            raise HTTPException(400, f"Продукт '{item.name}' уже существует")
        db_item = Product(
            name=item.name.strip(),
            unit=(item.unit or "").strip(),
            category=(item.category or "").strip()
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return {"id": db_item.id, "name": db_item.name, "unit": db_item.unit, "category": db_item.category}
    finally:
        db.close()


@app.put("/api/products/{product_id}")
async def update_product(product_id: int, item: ProductCreate):
    db = SessionLocal()
    try:
        db_item = db.query(Product).filter(Product.id == product_id).first()
        if not db_item:
            raise HTTPException(404, "Продукт не найден")
        if not item.name.strip():
            raise HTTPException(400, "Название продукта не может быть пустым")
        existing = db.query(Product).filter(
            Product.name.ilike(item.name.strip()),
            Product.id != product_id
        ).first()
        if existing:
            raise HTTPException(400, f"Продукт '{item.name}' уже существует")
        db_item.name = item.name.strip()
        db_item.unit = (item.unit or "").strip()
        db_item.category = (item.category or "").strip()
        db.commit()
        db.refresh(db_item)
        return {"id": db_item.id, "name": db_item.name, "unit": db_item.unit, "category": db_item.category}
    finally:
        db.close()


@app.delete("/api/products/{product_id}")
async def delete_product(product_id: int):
    db = SessionLocal()
    try:
        db_item = db.query(Product).filter(Product.id == product_id).first()
        if not db_item:
            raise HTTPException(404, "Продукт не найден")
        db.delete(db_item)
        db.commit()
        return {"message": "Продукт удалён"}
    finally:
        db.close()


# ==================== API: СПИСОК ПОКУПОК ====================

@app.post("/api/shopping/generate")
async def generate_shopping_from_menu():
    """
    Функция 5. Формирование списка покупок с учетом количества порций.
    """
    db = SessionLocal()
    try:
        menu_items = db.query(Menu).all()
        # Создаем словарь: {dish_id: общее_количество_порций_в_меню}
        dish_servings = {}
        for m in menu_items:
            if m.dish_id:
                dish_servings[m.dish_id] = dish_servings.get(m.dish_id, 0) + (m.servings or 1)

        if not dish_servings:
            raise HTTPException(400, "В меню нет блюд — нечего собирать.")

        # Получаем все ингредиенты для этих блюд
        ingredients = db.query(Ingredient).filter(Ingredient.dish_id.in_(dish_servings.keys())).all()

        aggregated = {}
        for ing in ingredients:
            name = (ing.name or "").strip()
            unit = (ing.unit or "").strip()
            if not name:
                continue

            # Умножаем количество ингредиента на общее количество порций этого блюда
            total_servings = dish_servings.get(ing.dish_id, 1)
            
            key = (name.lower(), unit.lower())
            qty_num, qty_text = parse_quantity(ing.quantity)
            
            if key not in aggregated:
                aggregated[key] = {
                    "name": name,
                    "unit": unit,
                    "qty": 0.0,
                    "has_numeric": False,
                    "text_qty": []
                }
            
            if qty_num is not None:
                # Умножаем!
                aggregated[key]["qty"] += qty_num * total_servings
                aggregated[key]["has_numeric"] = True
            elif qty_text:
                # Если количество текстовое (например "по вкусу"), просто добавляем текст
                # (умножать текст не имеет смысла)
                aggregated[key]["text_qty"].append(f"{qty_text} (x{total_servings})")

        db.query(Shopping).delete()

        for key, data in aggregated.items():
            if data["has_numeric"]:
                q = data["qty"]
                qty_str = str(int(q)) if q == int(q) else f"{q:g}"
                if data["text_qty"]:
                    qty_str += " (+ " + ", ".join(data["text_qty"]) + ")"
            else:
                qty_str = ", ".join(data["text_qty"]) if data["text_qty"] else ""

            db.add(Shopping(
                item_text=f"{data['name']} — {qty_str} {data['unit']}".strip(),
                name=data["name"],
                quantity=qty_str,
                unit=data["unit"],
                bought=0,
                category=""
            ))

        db.commit()
        count = db.query(Shopping).count()
        return {"message": f"Сформировано {count} позиций для покупки (с учетом порций)."}
    finally:
        db.close()


@app.get("/api/shopping")
async def get_shopping():
    db = SessionLocal()
    try:
        items = db.query(Shopping).order_by(Shopping.name).all()
        return [{
            "id": i.id,
            "name": i.name or i.item_text or "",
            "quantity": i.quantity or "",
            "unit": i.unit or "",
            "bought": i.bought or 0,
            "category": i.category or ""
        } for i in items]
    finally:
        db.close()


@app.post("/api/shopping")
async def create_shopping_item(item: ShoppingItemCreate):
    db = SessionLocal()
    try:
        if not item.name.strip():
            raise HTTPException(400, "Название не может быть пустым")
        db_item = Shopping(
            item_text=item.name.strip(),
            name=item.name.strip(),
            quantity=(item.quantity or "").strip(),
            unit=(item.unit or "").strip(),
            bought=0,
            category=(item.category or "").strip()
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return {
            "id": db_item.id, "name": db_item.name, "quantity": db_item.quantity,
            "unit": db_item.unit, "bought": db_item.bought, "category": db_item.category
        }
    finally:
        db.close()


@app.put("/api/shopping/{item_id}")
async def update_shopping_item(item_id: int, item: ShoppingItemUpdate):
    db = SessionLocal()
    try:
        db_item = db.query(Shopping).filter(Shopping.id == item_id).first()
        if not db_item:
            raise HTTPException(404, "Позиция не найдена")
        if item.name is not None:
            db_item.name = item.name.strip()
            db_item.item_text = item.name.strip()
        if item.quantity is not None:
            db_item.quantity = item.quantity.strip()
        if item.unit is not None:
            db_item.unit = item.unit.strip()
        if item.category is not None:
            db_item.category = item.category.strip()
        if item.bought is not None:
            db_item.bought = 1 if item.bought else 0
        db.commit()
        db.refresh(db_item)
        return {
            "id": db_item.id, "name": db_item.name, "quantity": db_item.quantity,
            "unit": db_item.unit, "bought": db_item.bought, "category": db_item.category
        }
    finally:
        db.close()


@app.patch("/api/shopping/{item_id}/toggle")
async def toggle_shopping_bought(item_id: int):
    db = SessionLocal()
    try:
        db_item = db.query(Shopping).filter(Shopping.id == item_id).first()
        if not db_item:
            raise HTTPException(404, "Позиция не найдена")
        db_item.bought = 0 if (db_item.bought or 0) else 1
        db.commit()
        db.refresh(db_item)
        return {"id": db_item.id, "bought": db_item.bought}
    finally:
        db.close()


@app.delete("/api/shopping/{item_id}")
async def delete_shopping_item(item_id: int):
    db = SessionLocal()
    try:
        db_item = db.query(Shopping).filter(Shopping.id == item_id).first()
        if not db_item:
            raise HTTPException(404, "Позиция не найдена")
        db.delete(db_item)
        db.commit()
        return {"message": "Позиция удалена"}
    finally:
        db.close()


@app.delete("/api/shopping")
async def clear_shopping():
    db = SessionLocal()
    try:
        db.query(Shopping).delete()
        db.commit()
        return {"message": "Список покупок очищен"}
    finally:
        db.close()


@app.get("/api/shopping/export")
async def export_shopping():
    """Возвращает только некупленные позиции (итоговый список к покупке)."""
    db = SessionLocal()
    try:
        items = db.query(Shopping).filter(Shopping.bought == 0).order_by(Shopping.name).all()
        return [{
            "name": i.name or i.item_text or "",
            "quantity": i.quantity or "",
            "unit": i.unit or ""
        } for i in items]
    finally:
        db.close()


# ==================== API: ПОЛНЫЙ ОТЧЁТ ====================

@app.get("/api/report")
async def get_report():
    db = SessionLocal()
    try:
        menu_items = db.query(Menu).order_by(Menu.date, Menu.meal_type).all()
        dish_ids = list({m.dish_id for m in menu_items if m.dish_id})
        ingredients_by_dish = {}
        if dish_ids:
            ings = db.query(Ingredient).filter(Ingredient.dish_id.in_(dish_ids)).all()
            for ing in ings:
                ingredients_by_dish.setdefault(ing.dish_id, []).append({
                    "name": ing.name, "quantity": ing.quantity, "unit": ing.unit
                })
        days = {}
        for m in menu_items:
            days.setdefault(m.date, {})
            days[m.date][m.meal_type] = {
                "dish_id": m.dish_id,
                "dish_name": m.text,
                "servings": m.servings or 1,
                "ingredients": ingredients_by_dish.get(m.dish_id, [])
            }
        aggregated = {}
        for m in menu_items:
            for ing in ingredients_by_dish.get(m.dish_id, []):
                key = (ing["name"], ing["unit"] or "")
                try:
                    qty = float(ing["quantity"]) if ing["quantity"] else 0
                except ValueError:
                    qty = 0
                # Умножаем на порции в отчете
                aggregated[key] = aggregated.get(key, 0) + (qty * (m.servings or 1))
        summary = [{"name": k[0], "unit": k[1], "quantity": v} for k, v in aggregated.items()]
        return {
            "days": days,
            "summary": summary,
            "generated_at": datetime.now().isoformat()
        }
    finally:
        db.close()


# ==================== API: ОЧИСТКА ====================

@app.post("/api/clear")
async def clear_all():
    db = SessionLocal()
    try:
        db.query(Menu).delete()
        db.query(Shopping).delete()
        db.commit()
        return {"message": "Очищено"}
    finally:
        db.close()

@app.get("/api/shopping/export/strategy")
async def export_shopping_strategy(format: str = "txt"):
    db = SessionLocal()
    try:
        items = db.query(Shopping).filter(Shopping.bought == 0).all()
        data = [{"name": i.name, "quantity": i.quantity, "unit": i.unit} for i in items]

        # Выбор стратегии из реестра (паттерн «Стратегия», OCP)
        return {"data": get_strategy(format).export(data)}
    finally:
        db.close()

import uvicorn
import logging
import webbrowser
import threading

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threading.Timer(1.5, lambda: webbrowser.open('http://localhost:8000')).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)
