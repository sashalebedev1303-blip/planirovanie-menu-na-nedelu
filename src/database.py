import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

BASE_DIR = Path(__file__).parent
# ЛР-9: путь к БД можно переопределить (в контейнере — /app/data/dacha.db,
# каталог монтируется томом, поэтому данные переживают пересоздание образа).
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "dacha.db")))
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
