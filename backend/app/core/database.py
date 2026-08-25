import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# o .env fica na raiz do projeto, quatro niveis acima deste arquivo
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL nao definida no .env")

# echo=True imprime todo SQL gerado - otimo para aprender, desligue depois
engine = create_engine(DATABASE_URL, echo=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """Classe-mae de todos os models. O Alembic descobre as tabelas por ela."""


def get_db():
    """Dependency do FastAPI: abre uma sessao por request e fecha no fim."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
