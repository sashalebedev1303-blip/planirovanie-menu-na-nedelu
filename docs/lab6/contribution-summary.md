# Сводка вклада участников (ЛР-6)

## Как посмотреть на GitHub

- **Insights → Contributors** — диаграмма коммитов по участникам:
  https://github.com/sashalebedev1303-blip/planirovanie-menu-na-nedelu/graphs/contributors
- **Insights → Pulse** — сводка периода: https://github.com/sashalebedev1303-blip/planirovanie-menu-na-nedelu/pulse
- ** команда → Insights → Network** — карта веток и слияний.

## Количественная сводка (на момент ветки `feature/lab6-git-workflow`)

| Участник | Аккаунт | Коммитов (всего) | Вклад в ЛР-6 |
|---|---|---|---|
| Николаев Игорь Олегович | @IgrokY (tapshark93@gmail.com) | 52 | pre-commit хук с ruff; рефакторинг: модули `export_strategies.py`, `quantity.py`; разделы CONTRIBUTING; демо `git bisect`/`reflog` |
| Лебедев Александр Витальевич | @sashalebedev1303-blip (sashalebedev1303@gmail.com) | 217 | слои SOLID (`database.py`, `models.py`, `schemas.py`); стратегия экспорта в коде; отчёт о рефакторинге; разрешение конфликта; тесты; сводка вклада и заметки о версии |

«Вклад в ЛР-6» проверяется по истории PR:

| PR | Ветка | Кто вёл | Что сделано |
|---|---|---|---|
| #99 | `create_ruff_check` | Игорь | линтер ruff в CI; **конфликт** по `ruff.toml` разрешён в веб-интерфейсе (см. `docs/conflict-resolution.md`) |
| #100 | `create-build.app` | Лебедев | скрипт сборки `src/build_app.py` |
| #101 | `new_dishes` | Лебедев | расширение справочника блюд (`src/dishes.csv` до 2373 строк) |
| #102 | `feature/solid-refactoring_original` | Лебедев | SOLID-рефакторинг (слои), паттерн «Стратегия», `docs/refactoring.md` |
| PR ветки `feature/lab6-git-workflow` | `feature/lab6-git-workflow` | оба (4 коммита Игорь, 3 коммита Лебедев) | pre-commit, тесты, демо bisect/reflog, версии/теги, сводка вклада |

Локальная проверка:

```
> git shortlog -sne HEAD
  217  sashalebedev1303-blip
   52  Игорь
    4  Николаев Игорь Олегович   ← серия коммитов ЛР-6
    1  Лебедев Александр Витальевич ← серия коммитов ЛР-6
```

## Качественная сводка

- Каждый участник в ЛР-6 вёл свою задачу и коммиты в специально
  отведённых ветках, изменения попадали в `main` через PR (#99–#102).
- Ревью — по чек-листу методички: решает ли изменение задачу, понятны
  имена, нет дублирования, обработаны ошибки, есть тесты.
- Роли: Игорь — тимлид/разработчик, Лебедев — аналитик/тестировщик
  (ротация зафиксирована в CONTRIBUTING.md, раздел «Роли и ротация»).
