from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ambientes.models import Ambiente


def buscar_por_nome(db: Session, nome: str) -> Ambiente | None:
    query = select(Ambiente).where(Ambiente.nome == nome)
    return db.scalars(query).first()


def salvar(db: Session, ambiente: Ambiente) -> Ambiente:
    db.add(ambiente)
    db.commit()
    return ambiente
