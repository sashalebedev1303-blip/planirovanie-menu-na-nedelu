"""Генерация презентации защиты проекта (ЛР-9).

Запуск: ``python scripts/build_presentation.py``
Результат: ``docs/presentation.pptx`` — 7 слайдов по требованиям методички
(проблема, требования, решение, инженерный процесс, метрики, демонстрация).
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "presentation.pptx"

NAVY = RGBColor(0x1B, 0x2A, 0x4A)
BLUE = RGBColor(0x19, 0x76, 0xD2)
GREEN = RGBColor(0x2E, 0x7D, 0x32)
ORANGE = RGBColor(0xEF, 0x6C, 0x00)
TEAL = RGBColor(0x00, 0x89, 0x7B)
GRAY = RGBColor(0x5F, 0x6B, 0x7A)
LIGHT = RGBColor(0xF2, 0xF5, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def add_textbox(slide, left, top, width, height, text, size=18, color=NAVY,
                bold=False, align=PP_ALIGN.LEFT, font="Segoe UI"):
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font
    return box


def add_bullets(slide, left, top, width, height, items, size=17,
                color=NAVY, spacing=Pt(8)):
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    for index, item in enumerate(items):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.space_after = spacing
        run = paragraph.add_run()
        run.text = f"•  {item}"
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.name = "Segoe UI"
    return box


def add_rect(slide, left, top, width, height, fill, line=None, radius=False):
    shape_type = 5 if radius else 1  # MSO_SHAPE.ROUNDED_RECTANGLE / RECTANGLE
    shape = slide.shapes.add_shape(shape_type, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(1.5)
    shape.shadow.inherit = False
    return shape


def slide_base(prs, title, number, kicker=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_rect(slide, 0, 0, SLIDE_W, Inches(0.18), NAVY)
    add_rect(slide, 0, Inches(0.18), Inches(2.4), Inches(0.05), ORANGE)
    if kicker:
        add_textbox(slide, Inches(0.7), Inches(0.42), Inches(11), Inches(0.3),
                    kicker.upper(), size=11, color=ORANGE, bold=True)
    add_textbox(slide, Inches(0.7), Inches(0.7), Inches(11.9), Inches(0.8),
                title, size=30, color=NAVY, bold=True)
    add_textbox(slide, Inches(0.7), Inches(6.95), Inches(9), Inches(0.3),
                "TastyWeek · ЛР-9 «CI/CD и релиз» · 2026", size=10, color=GRAY)
    add_textbox(slide, Inches(12.1), Inches(6.95), Inches(0.6), Inches(0.3),
                str(number), size=10, color=GRAY, align=PP_ALIGN.RIGHT)
    return slide


def add_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def slide_title(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, NAVY)
    add_rect(slide, 0, Inches(4.55), SLIDE_W, Inches(0.06), ORANGE)
    add_textbox(slide, Inches(0.9), Inches(1.35), Inches(11.5), Inches(1.0),
                "🍽️  TastyWeek", size=54, color=WHITE, bold=True)
    add_textbox(slide, Inches(0.95), Inches(2.35), Inches(11.5), Inches(0.9),
                "ИС планирования меню на неделю", size=32, color=RGBColor(0xC9, 0xD6, 0xEA))
    add_textbox(slide, Inches(0.95), Inches(3.35), Inches(11.5), Inches(0.6),
                "Защита сквозного проекта: от требований до релиза v1.0.0",
                size=20, color=RGBColor(0xC9, 0xD6, 0xEA))
    add_textbox(slide, Inches(0.95), Inches(4.85), Inches(11.5), Inches(1.3),
                "Николаев Игорь Олегович — тимлид, разработчик\n"
                "Лебедев Александр Витальевич — аналитик, тестировщик\n"
                "«Программная инженерия», 3 курс, 2026/2027",
                size=16, color=WHITE)
    add_notes(slide, "Представление команды и цели: показать полный инженерный "
                     "цикл — от проблемы до работающего релиза.")
    return slide


def slide_problem(prs):
    slide = slide_base(prs, "Проблема и пользователи", 2, "Зачем продукт")
    add_bullets(slide, Inches(0.75), Inches(1.75), Inches(7.2), Inches(4.4), [
        "Домашнее меню на неделю планируется вручную: 40–60 минут каждую неделю.",
        "Ингредиенты забываются, продукты покупаются дважды или остаются лишними.",
        "Нет единого места, где меню, рецепты и список покупок связаны между собой.",
        "Пользователи: студенты, сотрудники и все, кто ведёт домашнее хозяйство.",
        "Цель MVP (v0.1) → релиз v1.0.0: сократить планирование до нескольких минут и получить точный список покупок.",
    ], size=17)

    cards = [
        ("40–60", "минут вручную\nна неделю", ORANGE),
        ("5", "ключевых функций\nпервого релиза", BLUE),
        ("1", "пользователь — одна\nлокальная база", TEAL),
    ]
    for index, (value, caption, color) in enumerate(cards):
        left = Inches(8.35)
        top = Inches(1.85 + index * 1.55)
        add_rect(slide, left, top, Inches(4.2), Inches(1.3), LIGHT, radius=True)
        add_rect(slide, left, top, Inches(0.12), Inches(1.3), color)
        add_textbox(slide, left + Inches(0.3), top + Inches(0.12), Inches(1.5),
                    Inches(0.7), value, size=30, color=color, bold=True)
        add_textbox(slide, left + Inches(1.75), top + Inches(0.2), Inches(2.3),
                    Inches(0.9), caption, size=13, color=NAVY)
    add_notes(slide, "Проблема измерена в часах; пользователь один, база локальная — "
                     "границы MVP честно обозначены.")
    return slide


def slide_requirements(prs):
    slide = slide_base(prs, "Требования и границы MVP", 3, "Что обещали")
    add_bullets(slide, Inches(0.75), Inches(1.8), Inches(6.0), Inches(4.5), [
        "Составление меню по дням: 4 приёма пищи и количество порций.",
        "Справочник блюд с ингредиентами и справочник продуктов.",
        "Автоматический сводный список покупок с учётом порций.",
        "Отметка купленного, ручное редактирование, экспорт TXT/CSV, печать.",
        "Поиск блюд по названию и категории.",
    ], size=17)

    add_rect(slide, Inches(7.1), Inches(1.75), Inches(5.45), Inches(4.5), LIGHT, radius=True)
    add_textbox(slide, Inches(7.4), Inches(1.95), Inches(4.9), Inches(0.4),
                "Проверяемость требований", size=18, color=NAVY, bold=True)
    add_bullets(slide, Inches(7.4), Inches(2.45), Inches(4.85), Inches(3.5), [
        "User stories и SRS — docs/requirements/.",
        "Матрица прослеживаемости: история → требование → задача → ветка.",
        "43 автотеста, включая интеграционные сценарии API.",
        "Definition of Done: ревью, зелёный CI, тесты, документация.",
    ], size=14, color=GRAY, spacing=Pt(6))
    add_notes(slide, "Показать, что требования не «на словах»: SRS, user stories, "
                     "матрица прослеживаемости и тесты.")
    return slide


def slide_architecture(prs):
    slide = slide_base(prs, "Решение и архитектура", 4, "Как устроено")
    boxes = [
        ("Веб-интерфейс", "HTML + CSS + JS\nChoices.js, адаптивная вёрстка", BLUE, 0.8),
        ("API-сервер", "FastAPI · 30 маршрутов\nSQLAlchemy ORM", GREEN, 4.85),
        ("База данных", "SQLite · dacha.db\n6 сущностей", TEAL, 8.9),
    ]
    for title, subtitle, color, left in boxes:
        add_rect(slide, Inches(left), Inches(1.9), Inches(3.4), Inches(1.55), color, radius=True)
        add_textbox(slide, Inches(left + 0.2), Inches(2.05), Inches(3.0), Inches(0.45),
                    title, size=20, color=WHITE, bold=True)
        add_textbox(slide, Inches(left + 0.2), Inches(2.55), Inches(3.0), Inches(0.8),
                    subtitle, size=12, color=WHITE)
    for left in (4.25, 8.3):
        add_textbox(slide, Inches(left), Inches(2.35), Inches(0.55), Inches(0.5),
                    "→", size=28, color=ORANGE, bold=True)

    add_bullets(slide, Inches(0.8), Inches(3.9), Inches(11.8), Inches(2.6), [
        "Монолит с чётким разделением слоёв: database → models → schemas → main (ADR-002).",
        "Выбор SQLite зафиксирован в ADR-001: локальный однопользовательский режим, ноль администрирования.",
        "Паттерн «Стратегия» для экспорта списка покупок — расширение без правки маршрутов (OCP).",
        "Схема БД, C4-модель, UML-диаграммы — docs/architecture/ и docs/uml/.",
    ], size=15, color=NAVY)
    add_notes(slide, "Объяснить, почему монолит и SQLite: масштаб продукта и стоимость "
                     "администрирования; решения оформлены ADR.")
    return slide


def slide_process(prs):
    slide = slide_base(prs, "Инженерный процесс", 5, "Как работали")
    steps = [
        ("Scrum", "2 спринта,\nпланёрки и ретро", BLUE),
        ("GitHub Flow", "ветка → PR →\nревью → main", GREEN),
        ("CI/CD", "lint → tests →\nbuild → docker", ORANGE),
        ("Релизы", "SemVer, теги,\nRelease Notes", TEAL),
    ]
    for index, (title, subtitle, color) in enumerate(steps):
        left = 0.75 + index * 3.1
        add_rect(slide, Inches(left), Inches(1.85), Inches(2.75), Inches(1.35), color, radius=True)
        add_textbox(slide, Inches(left + 0.15), Inches(1.98), Inches(2.45), Inches(0.4),
                    title, size=19, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        add_textbox(slide, Inches(left + 0.15), Inches(2.45), Inches(2.45), Inches(0.6),
                    subtitle, size=12, color=WHITE, align=PP_ALIGN.CENTER)

    add_bullets(slide, Inches(0.8), Inches(3.65), Inches(11.8), Inches(2.8), [
        "Прямые коммиты в main запрещены правилами команды: изменение — через pull request и ревью второго участника.",
        "Конвейер — это код: workflow лежит в репозитории и ревьюится как любой другой артефакт.",
        "После включения защиты ветки красный статус блокирует слияние: обязательны lint, tests, build, docker.",
        "Документация живёт рядом с кодом: ADR, протоколы встреч, реестр долга, заметки релиза.",
        "Вклад участников фиксируется историей коммитов, PR и протоколами (docs/team-contributions.md).",
    ], size=15, color=NAVY)
    add_notes(slide, "Подчеркнуть: процесс не формальность — он виден в истории репозитория "
                     "и в зелёных проверках PR.")
    return slide


def slide_metrics(prs):
    slide = slide_base(prs, "Метрики качества", 6, "Что измеряли")
    metrics = [
        ("43", "автотеста, все зелёные", GREEN),
        ("100 %", "покрытие ключевых модулей\nпри пороге 60 %", BLUE),
        ("0", "замечаний ruff\nв строгом профиле", ORANGE),
        ("21 → 12", "максимальная цикломатическая\nсложность после рефакторинга", TEAL),
        ("4,1 → 3,6 %", "дублирование кода", BLUE),
        ("4", "позиции техдолга погашены\nс измеримым эффектом", GREEN),
    ]
    for index, (value, caption, color) in enumerate(metrics):
        row, column = divmod(index, 3)
        left = Inches(0.75 + column * 4.1)
        top = Inches(1.85 + row * 2.25)
        add_rect(slide, left, top, Inches(3.8), Inches(1.95), LIGHT, radius=True)
        add_rect(slide, left, top, Inches(3.8), Inches(0.1), color)
        add_textbox(slide, left + Inches(0.2), top + Inches(0.25), Inches(3.4),
                    Inches(0.7), value, size=30, color=color, bold=True)
        add_textbox(slide, left + Inches(0.2), top + Inches(1.05), Inches(3.4),
                    Inches(0.8), caption, size=13, color=NAVY)

    add_textbox(slide, Inches(0.8), Inches(6.25), Inches(11.8), Inches(0.5),
                "Замеры и обоснования: docs/quality/ · реестр долга: docs/debt/",
                size=12, color=GRAY)
    add_notes(slide, "Метрики сравниваются «до/после» внутри команды; покрытие честно "
                     "ограничено ключевыми вычислительными модулями. Если спросят про "
                     "ограничения — назвать SQLite и одного пользователя, HTML-шаблон "
                     "в main.py и остаточный долг (docs/debt/accepted-debt.md).")
    return slide


def slide_demo(prs):
    slide = slide_base(prs, "Демонстрация и релиз v1.0.0", 7, "Путь изменения")
    stages = [
        ("Коммит", "ветка\nfeature/*"),
        ("Pull Request", "ревью +\nобсуждение"),
        ("CI", "lint · tests\nbuild · docker"),
        ("Артефакт", "zip + образ\nGHCR"),
        ("Релиз", "тег v1.0.0\nRelease Notes"),
    ]
    for index, (title, subtitle) in enumerate(stages):
        left = 0.55 + index * 2.55
        color = [BLUE, BLUE, ORANGE, GREEN, TEAL][index]
        add_rect(slide, Inches(left), Inches(1.85), Inches(2.15), Inches(1.25), color, radius=True)
        add_textbox(slide, Inches(left + 0.1), Inches(1.98), Inches(1.95), Inches(0.4),
                    title, size=15, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        add_textbox(slide, Inches(left + 0.1), Inches(2.4), Inches(1.95), Inches(0.6),
                    subtitle, size=10, color=WHITE, align=PP_ALIGN.CENTER)
        if index < len(stages) - 1:
            add_textbox(slide, Inches(left + 2.16), Inches(2.25), Inches(0.4), Inches(0.4),
                        "→", size=18, color=GRAY, bold=True)

    add_rect(slide, Inches(0.8), Inches(3.5), Inches(5.6), Inches(2.6), LIGHT, radius=True)
    add_textbox(slide, Inches(1.05), Inches(3.65), Inches(5.1), Inches(0.4),
                "Что показывает конвейер", size=17, color=NAVY, bold=True)
    add_bullets(slide, Inches(1.05), Inches(4.1), Inches(5.1), Inches(1.9), [
        "4 job'а с зависимостями needs.",
        "Артефакт tastyweek-app в каждом прогоне.",
        "Smoke-тест образа: docker run + /api/menu.",
        "Публикация в GHCR на main и теге v*.",
    ], size=13, color=GRAY, spacing=Pt(4))

    add_rect(slide, Inches(6.85), Inches(3.5), Inches(5.7), Inches(2.6), NAVY, radius=True)
    add_textbox(slide, Inches(7.1), Inches(3.65), Inches(5.2), Inches(0.4),
                "Запуск релиза", size=17, color=WHITE, bold=True)
    add_textbox(slide, Inches(7.1), Inches(4.15), Inches(5.2), Inches(1.7),
                "docker pull ghcr.io/sashalebedev1303-blip/\\\n"
                "  planirovanie-menu-na-nedelu:1.0.0\n\n"
                "docker run -p 8000:8000 \\\n"
                "  -v tastyweek-data:/app/data \\\n"
                "  ghcr.io/sashalebedev1303-blip/\\\n"
                "  planirovanie-menu-na-nedelu:1.0.0",
                size=10, color=RGBColor(0xC9, 0xD6, 0xEA), font="Consolas")
    add_notes(slide, "Кульминация: живой прогон PR → CI → артефакт → образ → релиз. "
                     "Показать страницу релиза и скачать артефакт.")
    return slide


def build() -> Path:
    prs = Presentation()
    prs.slide_width = Emu(SLIDE_W)
    prs.slide_height = Emu(SLIDE_H)
    slide_title(prs)
    slide_problem(prs)
    slide_requirements(prs)
    slide_architecture(prs)
    slide_process(prs)
    slide_metrics(prs)
    slide_demo(prs)
    prs.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    path = build()
    print(f"Презентация собрана: {path.relative_to(ROOT)}")
