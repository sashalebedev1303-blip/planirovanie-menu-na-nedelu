"""Паттерн «Стратегия»: выгрузка списка покупок в разных форматах.

Модуль изолирует алгоритмы экспорта (SOLID, SRP) от маршрутов FastAPI.
Новый формат добавляется одним классом и одной строкой в реестре
STRATEGIES — существующий код не изменяется (SOLID, OCP).
"""
import csv
import io
from abc import ABC, abstractmethod

class ExportStrategy(ABC):
    """Общий интерфейс всех стратегий экспорта."""

    @abstractmethod
    def export(self, items: list) -> str:
        """Формирует текстовое представление списка позиций."""

class TxtExportStrategy(ExportStrategy):
    """Выгрузка списка покупок в обычный текст (TXT)."""

    def export(self, items: list) -> str:
        result = "СПИСОК ПОКУПОК\n" + "=" * 30 + "\n"
        for i, item in enumerate(items, 1):
            result += f"{i}. {item['name']} — {item['quantity']} {item['unit']}\n"
        return result

class CsvExportStrategy(ExportStrategy):
    """Выгрузка списка покупок в CSV (разделитель «;», Excel)."""

    def export(self, items: list) -> str:
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(["Наименование", "Количество", "Ед.изм"])
        for item in items:
            writer.writerow([item["name"], item["quantity"], item["unit"]])
        return output.getvalue()

# Реестр стратегий: ключ — формат формата запроса.
# Чтобы поддержать новый формат, достаточно добавить класс и строку здесь.
STRATEGIES: dict[str, ExportStrategy] = {
    "txt": TxtExportStrategy(),
    "csv": CsvExportStrategy(),
}

def get_strategy(fmt: str) -> ExportStrategy:
    """Возвращает стратегию по формату; по умолчанию — TXT."""
    return STRATEGIES.get(fmt.lower(), STRATEGIES["txt"])
