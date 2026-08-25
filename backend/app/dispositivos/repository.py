from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ambientes.models import Ambiente
from app.dispositivos.models import Dispositivo


def buscar_por_codigo(db: Session, codigo: str) -> Dispositivo | None:
    query = select(Dispositivo).where(Dispositivo.codigo == codigo)
    return db.scalars(query).first()


def buscar_ambiente(db: Session, ambiente_id: int) -> Ambiente | None:
    return db.get(Ambiente, ambiente_id)


def salvar(db: Session, dispositivo: Dispositivo) -> Dispositivo:
    db.add(dispositivo)
    db.commit()
    return dispositivo
