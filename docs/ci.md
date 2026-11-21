# Конвейер CI/CD и защита основной ветки (ЛР-9)

Документ описывает, как устроен конвейер проекта, какие проверки обязательны
для слияния в `main` и как воспроизвести пайплайн локально.

## 1. Что запускается и когда

Конвейер описан в [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
(«конвейер — это код»: изменения проверок проходят через PR, как и любой код).

| Событие | Что выполняется |
|---|---|
| `pull_request` → `main` | `lint` → `tests` → `build` → `docker` (образ собирается, запускается и проходит smoke-тест) |
| `push` в `main` | те же job'ы + публикация образа в GHCR |
| `push` тега `v*` | те же job'ы + публикация образа с версией (`1.0.0`, `1.0`) |
| `workflow_dispatch` | ручной прогон для демонстрации «путь изменения» |

Порядок job'ов задан зависимостями `needs`: сборка не начнётся, пока не
позеленели линтер и тесты; Docker-образ не собирается, пока не собрался
артефакт. Любой ненулевой код возврата роняет job, а красный статус
блокирует слияние (после настройки правил защиты, п. 3).

### Job'ы и их имена

| Job (имя статус-проверки) | Что делает | Артефакт |
|---|---|---|
| `lint` | `ruff check .` по конфигурации `ruff.toml` | — |
| `tests` | `pytest -v` (43 теста, покрытие ключевых модулей 100 %, порог 60 %) | отчёт в логе |
| `build` | `python scripts/build_release.py` — воспроизводимый zip приложения | `tastyweek-app` (30 дней) |
| `docker` | `docker build` + `docker run` + запрос `/api/menu` (smoke-тест) | образ в GHCR на `main`/теге |

Имена `lint`, `tests`, `build`, `docker` нужно указать в правилах защиты
ветки — именно так GitHub называет статус-проверки.

### Кэш и воспроизводимость

- `actions/setup-python` кэширует pip по `requirements-dev.txt` и
  `src/requirements.txt`;
- Docker-слои кэшируются через `cache-from/to: type=gha`; зависимости
  копируются в образ раньше кода, поэтому слой `pip install` не
  пересобирается при изменении исходников;
- артефакт сборки воспроизводим: файлы сортируются, дата внутри архива
  фиксирована, служебные каталоги и локальная БД исключены.

## 2. Локальное воспроизведение

```bash
# то же, что job lint
python -m pip install -r requirements-dev.txt
python -m ruff check .

# то же, что job tests
python -m pip install -r src/requirements.txt
python -m pytest -v

# то же, что job build
python scripts/build_release.py

# то же, что job docker (нужен Docker)
docker build -t tastyweek:v1.0.0 .
docker run --rm -p 8000:8000 -e OPEN_BROWSER=0 tastyweek:v1.0.0
# в другом терминале:
curl http://127.0.0.1:8000/api/menu
```

## 3. Защита ветки `main` (branch protection)

Требуется роль **Admin** в репозитории. Настройка выполняется один раз
владельцем репозитория и не хранится в коде — в репозитории фиксируется
только её описание (этот файл), как требует методичка.

### Вариант A. Rulesets (актуальный интерфейс GitHub)

1. **Settings → Rules → Rulesets → New branch ruleset**.
2. Название: `protect-main`; **Enforcement status**: `Active`.
3. **Target branches → Add target → Include default branch** (`main`).
4. Включить правила:
   - **Require a pull request before merging** → *Required approvals*: `1`;
   - **Require status checks to pass** → *Add checks*: `lint`, `tests`,
     `build`, `docker`; включить **Require branches to be up to date before
     merging**;
   - **Block force pushes**;
   - **Restrict deletions**.
5. **Create**.

### Вариант B. Классические Branch protection rules

1. **Settings → Branches → Add branch protection rule**.
2. *Branch name pattern*: `main`.
3. Включить:
   - **Require a pull request before merging** (1 approval,
     «Dismiss stale approvals» — по желанию);
   - **Require status checks to pass before merging** → выбрать `lint`,
     `tests`, `build`, `docker`; включить «Require branches to be up to date»;
   - **Do not allow bypassing the above settings** (запрет прямых push,
     включая администраторов);
   - **Do not allow force pushes** и **Do not allow deletions**.
4. **Create**.

После включения прямой `git push origin main` отклоняется, а PR с красным
конвейером нельзя слить: кнопка **Merge** заблокирована до зелёных проверок
и одобрения ревьюера.

> Проверка «красный блокирует слияние»: в демонстрационном PR достаточно
> сломать тест (например, `assert False`), дождаться красного `tests` и
> показать заблокированную кнопку Merge; затем откатить коммит.

## 4. Реестр образов (GHCR)

Образ публикуется в GitHub Container Registry:

```
ghcr.io/sashalebedev1303-blip/planirovanie-menu-na-nedelu:latest
ghcr.io/sashalebedev1303-blip/planirovanie-menu-na-nedelu:1.0.0
ghcr.io/sashalebedev1303-blip/planirovanie-menu-na-nedelu:sha-<коммит>
```

Публикация выполняется от `GITHUB_TOKEN` (права `packages: write`), отдельный
секрет не нужен. Первый пакет создаётся приватным: чтобы `docker pull`
работал без авторизации, владелец может открыть
**Profile → Packages → planirovanie-menu-na-nedelu → Package settings →
Change visibility → Public**. Для приватного пакета нужен
`docker login ghcr.io` с PAT (`read:packages`).

## 5. Артефакты работы

| Артефакт | Где лежит |
|---|---|
| Workflow конвейера | `.github/workflows/ci.yml` |
| Сборка релизного архива | `scripts/build_release.py` |
| Dockerfile и `.dockerignore` | корень репозитория |
| Заметки релиза v1.0.0 | `docs/release-notes/v1.0.0.md` |
| Демонстрация «путь изменения» | `docs/release-demo/README.md` + скриншоты |
| Презентация защиты | `docs/presentation.pptx` |
| Обратная связь репетиции | `docs/feedback.md` |

## 6. Известные ограничения

- Развёртывание в облаке не автоматизировано: по методичке достаточно
  локального запуска из контейнера, инструкция — в `README.md`.
- Публикация образа в GHCR требует, чтобы политика пакетов репозитория
  разрешала запись `GITHUB_TOKEN` (по умолчанию разрешена).
- Правила защиты ветки не версионируются вместе с кодом: их применение
  проверяется вручную по чек-листу из п. 3.
