from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ambientes.models import Ambiente


def buscar_por_id(db: Session, ambiente_id: int) -> Ambiente | None:
    return db.get(Ambiente, ambiente_id)


def buscar_por_nome(db: Session, nome: str) -> Ambiente | None:
    query = select(Ambiente).where(Ambiente.nome == nome)
    return db.scalars(query).first()


def listar(db: Session) -> list[Ambiente]:
    query = select(Ambiente).order_by(Ambiente.id)
    return list(db.scalars(query).all())


def salvar(db: Session, ambiente: Ambiente) -> Ambiente:
    db.add(ambiente)
    db.commit()
    return ambiente


def editar(db: Session, ambiente: Ambiente, campos: dict) -> Ambiente:
    for campo, valor in campos.items():
        setattr(ambiente, campo, valor)

    db.commit()
    return ambiente


def excluir(db: Session, ambiente: Ambiente) -> None:
    db.delete(ambiente)
    db.commit()
