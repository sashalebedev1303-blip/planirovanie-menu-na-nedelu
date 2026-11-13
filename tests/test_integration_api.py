"""Интеграционные тесты FastAPI-приложения (ЛР-7).

Проверяют совместную работу формы, валидации схемы, сохранения в БД
и расчёта списка покупок. Рабочая база dacha.db не затрагивается:
на время теста SessionLocal подменяется сессией с временной БД.
"""

import main
import pytest
from database import Base
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient с чистой SQLite-БД из tmp_path вместо рабочей dacha.db."""
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(main, "SessionLocal", TestSession)
    with TestClient(main.app) as test_client:
        yield test_client


def test_menu_form_validation_and_save(client):
    """Сценарий I1: форма «День меню» — валидация — сохранение."""
    # Валидация: произвольный приём пищи не принимается (баг-репорт № 3)
    resp = client.post("/api/menu", json={
        "date": "2026-11-05", "meal_type": "supper", "text": "Блины",
    })
    assert resp.status_code == 422

    # Корректная форма сохраняется
    resp = client.post("/api/menu", json={
        "date": "2026-11-05", "meal_type": "dinner", "text": "Блины", "servings": 2,
    })
    assert resp.status_code == 200

    # Граница № 20: повторное сохранение обновляет позицию, а не дублирует
    resp = client.post("/api/menu", json={
        "date": "2026-11-05", "meal_type": "dinner", "text": "Блины с творогом",
        "servings": 3,
    })
    assert resp.status_code == 200

    menu = client.get("/api/menu").json()
    assert len(menu) == 1
    assert menu[0]["text"] == "Блины с творогом"
    assert menu[0]["servings"] == 3


def test_menu_servings_to_shopping(client):
    """Сценарий I2: меню с порциями — расчёт — список покупок."""
    dish = client.post("/api/dishes", json={
        "name": "Овсянка", "category": "breakfast",
        "ingredients": [
            {"name": "Овсянка", "quantity": "80", "unit": "г"},
            {"name": "Молоко", "quantity": "0,25", "unit": "л"},
        ],
    }).json()
    dish_id = dish["id"]

    # Блюдо в меню два раза: 2 и 3 порции — суммарно 5
    client.post("/api/menu", json={
        "date": "2026-11-05", "meal_type": "breakfast",
        "text": "Овсянка", "dish_id": dish_id, "servings": 2,
    })
    client.post("/api/menu", json={
        "date": "2026-11-06", "meal_type": "breakfast",
        "text": "Овсянка", "dish_id": dish_id, "servings": 3,
    })

    resp = client.post("/api/shopping/generate")
    assert resp.status_code == 200

    items = {i["name"]: i for i in client.get("/api/shopping").json()}
    assert items["Овсянка"]["quantity"] == "400"   # 80 г × 5 порций
    assert items["Молоко"]["quantity"] == "1,25"   # 0,25 × 5; дробное — через запятую (баг № 1)


def test_report_counts_comma_decimal_quantities(client):
    """Сценарий I3: полный отчёт считает количества с запятой (баг-репорт № 2)."""
    dish = client.post("/api/dishes", json={
        "name": "Каша", "category": "lunch",
        "ingredients": [{"name": "Молоко", "quantity": "50,5", "unit": "мл"}],
    }).json()
    client.post("/api/menu", json={
        "date": "2026-11-05", "meal_type": "lunch",
        "text": "Каша", "dish_id": dish["id"], "servings": 2,
    })

    report = client.get("/api/report").json()
    summary = {s["name"]: s for s in report["summary"]}
    assert summary["Молоко"]["quantity"] == 101   # «50,5» × 2; раньше считалось 0
