# Прогон SonarQube Community Build (ЛР-8, верификация)

Дополнительная проверка метрик качества **настоящим SonarQube** — в противовес
основному профилю ruff. Сервер поднимается контейнером прямо на раннере
GitHub Actions, анализ выполняется там же, результаты выгружаются через REST API.

| Параметр | Значение |
|---|---|
| Сервер | SonarQube **9.9.8.100196** (LTS Community Build), Docker-образ `sonarqube:lts-community` |
| Проект | `tastyweek` (key), `TastyWeek` (name) |
| Анализируемое состояние | ветка `feature/lab8-quality-debt`, коммит `a55498d` (после погашения Д-1…Д-4) |
| Дата прогона | 18.11.2026 |
| Workflow | [`.github/workflows/sonarqube.yml`](../../../.github/workflows/sonarqube.yml) |
| Прогон | [Actions run #3](https://github.com/sashalebedev1303-blip/planirovanie-menu-na-nedelu/actions/runs/44343830230) |
| Объём анализа | 14 файлов, 2442 строк кода (ncloc) |

## Состав каталога

| Файл | Что внутри |
|---|---|
| `measures.json` | сводные метрики проекта (`/api/measures/component`) |
| `measures-tree.json` | метрики по файлам (`/api/measures/component_tree`) |
| `issues-code-smells.json` | все замечания с правилами и строками (`/api/issues/search`) |
| `issues-summary.json` | фасеты по правилам/серьёзности/типам |

## Как воспроизвести

**Через GitHub Actions (без локальной установки):**

1. вкладка **Actions** → workflow **SonarQube Analysis** → **Run workflow**;
2. прогон занимает 8–10 минут (из них анализ — 8 секунд, остальное: скачивание
   образа и старт сервера);
3. по завершении скачать артефакт **sonarqube-measures** (JSON с метриками и замечаниями).

**Локально через Docker:**

```bash
docker run -d --name sonarqube -p 9000:9000 \
  -v sonarqube_data:/opt/sonarqube/data \
  -v sonarqube_logs:/opt/sonarqube/logs \
  -v sonarqube_extensions:/opt/sonarqube/extensions \
  sonarqube:lts-community

# дождаться "status":"UP"
curl -s localhost:9000/api/system/status

# токен: My Account -> Security -> Generate token, затем
docker run --rm --network host \
  -e SONAR_HOST_URL=http://localhost:9000 -e SONAR_TOKEN=<токен> \
  -v "$PWD:/usr/src" sonarsource/sonar-scanner-cli \
  -Dsonar.projectKey=tastyweek -Dsonar.sources=src -Dsonar.tests=tests
```

## Ограничения этого прогона

1. **Эфемерность.** База (H2) живёт внутри контейнера раннера: дашборд после
   прогона недоступен, остаются только выгруженные JSON (и артефакты Actions —
   90 дней). Поэтому ключевые JSON продублированы в git.
2. **Community Build — одна ветка.** Анализ веток и PR-декорации — платные
   функции (Developer Edition), поэтому в Pull Request метрики не появляются.
3. **Покрытие не передавалось.** Порог команды (`pytest.ini`) измеряет только
   `shopping_calc` и `quantity` (100 %); передача такого отчёта в SonarQube
   показала бы заниженное покрытие по всему `src` (HTML-шаблон и маршруты
   покрытием не охвачены). Цифра покрытия остаётся за `pytest-cov`.
4. **Замер «до» этим инструментом не снимался** — состояние до рефакторингов
   измерено ruff-профилем и скриптом метрик (`docs/quality/metrics-before.json`).
