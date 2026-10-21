from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

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


def listar_dispositivos(db: Session) -> list[Dispositivo]:
    query = select(Dispositivo).order_by(Dispositivo.id)
    return list(db.scalars(query).all())


def listar_com_ambiente(db: Session) -> list[Dispositivo]:
    """Todos, ja com o ambiente carregado (o gateway precisa da zona)."""
    query = select(Dispositivo).options(joinedload(Dispositivo.ambiente))
    return list(db.scalars(query).all())


def editar_dispositivo(
    db: Session,
    dispositivo: Dispositivo,
    campos: dict,
) -> Dispositivo:
    for campo, valor in campos.items():
        setattr(dispositivo, campo, valor)

    db.commit()
    return dispositivo


def nome_valido(db: Session, nome: str) -> Dispositivo | None:
    query = select(Dispositivo).where(Dispositivo.nome == nome)
    return db.scalars(query).first()


def excluir_dispositivo(dispositivo: Dispositivo, db: Session) -> Dispositivo:
    dispositivo.ativo = False

    db.commit()
    return dispositivo
