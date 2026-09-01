from sqlalchemy.orm import Session

from app.dispositivos import repository
from app.dispositivos.exceptions import (
    AmbienteNaoEncontrado,
    CodigoJaCadastrado,
    DispositivoNaoEncontrado,
    NomeJaCadastrado,
)
from app.dispositivos.models import Dispositivo
from app.dispositivos.schemas import DispositivoCreate, DispositivoUpdate


def criar_dispositivo(db: Session, dados: DispositivoCreate) -> Dispositivo:
    codigo_exist = repository.buscar_por_codigo(db, dados.codigo)

    if codigo_exist is not None:
        raise CodigoJaCadastrado()

    ambiente_exist = repository.buscar_ambiente(db, dados.ambiente_id)

    if ambiente_exist is None:
        raise AmbienteNaoEncontrado()

    dispositivo = Dispositivo(
        codigo=dados.codigo,
        nome=dados.nome,
        ambiente_id=dados.ambiente_id,
    )

    return repository.salvar(db, dispositivo)

def listar_dispositivos(db: Session) -> list[Dispositivo] | None:
    dispositivos = repository.listar_dispositivos(db)

    return dispositivos

def buscar_por_codigo(codigo:str, db:Session)-> Dispositivo | None:
    dispositivo = repository.buscar_por_codigo(db, codigo)
    
    if dispositivo is None:
        raise DispositivoNaoEncontrado()
    
    return dispositivo

def editar_dispositivo(codigo: str, dados: DispositivoUpdate, db: Session) -> Dispositivo:
    dispositivo = repository.buscar_por_codigo(db, codigo)

    if dispositivo is None:
        raise DispositivoNaoEncontrado()

    # so os campos que o cliente REALMENTE mandou no corpo
    campos = dados.model_dump(exclude_unset=True)

    if "ambiente_id" in campos:
        ambiente = repository.buscar_ambiente(db, campos["ambiente_id"])
        if ambiente is None:
            raise AmbienteNaoEncontrado()

    if "nome" in campos:
        outro = repository.nome_valido(db, campos["nome"])
        if outro is not None and outro.id != dispositivo.id:
            raise NomeJaCadastrado()

    return repository.editar_dispositivo(db, dispositivo, campos)

def excluir_dispositivo(codigo:str, db:Session)->Dispositivo | None:
    dispositivo = repository.buscar_por_codigo(db, codigo)

    if dispositivo is None:
        raise DispositivoNaoEncontrado()
    
    return repository.excluir_dispositivo(dispositivo, codigo, db)