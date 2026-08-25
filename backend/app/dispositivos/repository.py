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

def listar_dispositivos(db:Session) ->Dispositivo | None:
    query = select(Dispositivo)
    dispositivos = db.scalars(query).all()
    
    return dispositivos

def editar_dispositivo(
    db: Session,
    dispositivo: Dispositivo,
    campos: dict,
) -> Dispositivo:
    for campo, valor in campos.items():
        setattr(dispositivo, campo, valor)

    db.commit()
    return dispositivo

def nome_valido(db: Session, nome:str)->Dispositivo | None:
    query = select(Dispositivo).where(Dispositivo.nome == nome)
    return db.scalars(query).first()

def excluir_dispositivo(dispositivo:Dispositivo, codigo:str, db:Session)->Dispositivo:
    setattr(dispositivo, "ativo",False )
    
    db.commit()
    return dispositivo