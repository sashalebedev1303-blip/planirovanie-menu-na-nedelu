"""Тесты паттерна «Стратегия» — экспорт списка покупок (ЛР-6)."""

from export_strategies import CsvExportStrategy, TxtExportStrategy, get_strategy

ITEMS = [
    {"name": "Яйца", "quantity": "9", "unit": "шт"},
    {"name": "Молоко", "quantity": "150", "unit": "мл"},
]


def test_txt_strategy_numbered_lines():
    text = TxtExportStrategy().export(ITEMS)
    assert text.startswith("СПИСОК ПОКУПОК")
    assert "1. Яйца — 9 шт\n" in text
    assert "2. Молоко — 150 мл\n" in text


def test_txt_strategy_empty_items():
    text = TxtExportStrategy().export([])
    assert text.startswith("СПИСОК ПОКУПОК")


def test_csv_strategy_header_and_rows():
    text = CsvExportStrategy().export(ITEMS)
    lines = text.strip().splitlines()
    assert lines[0] == "Наименование;Количество;Ед.изм"
    assert lines[1] == "Яйца;9;шт"
    assert lines[2] == "Молоко;150;мл"


def test_get_strategy_txt():
    strategy = get_strategy("txt")
    assert isinstance(strategy, TxtExportStrategy)
    assert "Яйца" in strategy.export(ITEMS)


def test_get_strategy_csv():
    assert isinstance(get_strategy("csv"), CsvExportStrategy)


def test_get_strategy_unknown_falls_back_to_txt():
    # Неизвестный формат не ломает эндпоинт: возвращается txt-стратегия
    assert isinstance(get_strategy("pdf"), TxtExportStrategy)
