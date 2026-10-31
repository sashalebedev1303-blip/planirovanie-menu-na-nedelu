"""Паттерн «Стратегия» (ЛР-6): стратегии экспорта списка покупок.

Модуль выделен из src/main.py, чтобы:

- стратегии не зависели от FastAPI и SQLAlchemy (чистые классы, SRP);
- HTML-роуты и алгоритмы экспорта менялись по разным причинам;
- стратегии можно было тестировать отдельно (tests/test_export_strategies.py);
- новый формат (например PDF) добавлялся новым классом без правки роутов (OCP).
"""

import csv
from abc import ABC, abstractmethod
from io import StringIO


class ExportStrategy(ABC):
    """Общий интерфейс всех стратегий экспорта списка покупок."""

    @abstractmethod
    def export(self, items: list) -> str:
        """Возвращает список позиций items в своём формате."""
        pass


class TxtExportStrategy(ExportStrategy):
    """Нумерованный текстовый список (для заметок и печати)."""

    def export(self, items: list) -> str:
        result = "СПИСОК ПОКУПОК\n" + "=" * 30 + "\n"
        for i, item in enumerate(items, 1):
            result += f"{i}. {item['name']} — {item['quantity']} {item['unit']}\n"
        return result


class CsvExportStrategy(ExportStrategy):
    """CSV с разделителем ';' — открывается в Excel."""

    def export(self, items: list) -> str:
        output = StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["Наименование", "Количество", "Ед.изм"])
        for item in items:
            writer.writerow([item["name"], item["quantity"], item["unit"]])
        return output.getvalue()


# Реестр стратегий (OCP): новый формат = новая запись в словаре,
# условные конструкции if/elif в коде не нужны.
STRATEGIES = {
    "txt": TxtExportStrategy,
    "csv": CsvExportStrategy,
}


def get_strategy(format_name: str) -> ExportStrategy:
    """Возвращает стратегию по имени формата; неизвестные форматы дают txt."""
    strategy_class = STRATEGIES.get(format_name, TxtExportStrategy)
    return strategy_class()
