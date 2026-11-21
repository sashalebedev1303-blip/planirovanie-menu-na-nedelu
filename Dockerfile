# syntax=docker/dockerfile:1
# ЛР-9: образ приложения «Помощник для планирования меню на неделю».
# Сборка:  docker build -t tastyweek:v1.0.0 .
# Запуск:  docker run -p 8000:8000 tastyweek:v1.0.0
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    OPEN_BROWSER=0 \
    DATABASE_PATH=/app/data/dacha.db

WORKDIR /app

# Зависимости копируются раньше кода: слой с pip install кэшируется,
# пока не изменится requirements.txt.
COPY src/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения и справочник блюд (dishes.csv лежит рядом с main.py).
COPY src/ ./

# Каталог для SQLite-базы: монтируется томом, чтобы данные жили вне контейнера.
RUN mkdir -p /app/data \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/menu', timeout=3)"

CMD ["python", "main.py"]
