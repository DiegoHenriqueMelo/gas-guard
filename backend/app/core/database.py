from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import DATABASE_URL, SQL_ECHO

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL nao definida")

# pool_pre_ping: testa a conexao antes de usar. Sem isto, depois que o
# Postgres reinicia a primeira query de cada conexao velha do pool falha.
engine = create_engine(DATABASE_URL, echo=SQL_ECHO, pool_pre_ping=True)

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
