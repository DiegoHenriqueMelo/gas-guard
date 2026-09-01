from sqlalchemy.orm import Session

from app.ambientes import repository
from app.ambientes.exceptions import (
    AmbienteNaoEncontrado,
    AmbientePossuiDispositivos,
    NomeJaCadastrado,
)
from app.ambientes.models import Ambiente
from app.ambientes.schemas import AmbienteCreate, AmbienteRead, AmbienteUpdate


def criar_ambiente(db: Session, dados: AmbienteCreate) -> Ambiente:
    if repository.buscar_por_nome(db, dados.nome) is not None:
        raise NomeJaCadastrado()

    ambiente = Ambiente(
        nome=dados.nome,
        descricao=dados.descricao,
    )

    return repository.salvar(db, ambiente)


def listar_ambientes(db: Session) -> list[Ambiente]:
    return repository.listar(db)


def buscar_ambiente(db: Session, ambiente_id: int) -> Ambiente:
    ambiente = repository.buscar_por_id(db, ambiente_id)

    if ambiente is None:
        raise AmbienteNaoEncontrado()

    return ambiente


def editar_ambiente(db: Session, ambiente_id: int, dados: AmbienteUpdate) -> Ambiente:
    ambiente = buscar_ambiente(db, ambiente_id)

    # so os campos que o cliente REALMENTE mandou no corpo
    campos = dados.model_dump(exclude_unset=True)

    if "nome" in campos:
        outro = repository.buscar_por_nome(db, campos["nome"])
        if outro is not None and outro.id != ambiente.id:
            raise NomeJaCadastrado()

    return repository.editar(db, ambiente, campos)


def excluir_ambiente(db: Session, ambiente_id: int) -> AmbienteRead:
    ambiente = buscar_ambiente(db, ambiente_id)

    # o ambiente e a chave estrangeira dos dispositivos: apagar com filhos
    # deixaria registros orfaos e o proprio banco recusaria o DELETE.
    if ambiente.dispositivos:
        raise AmbientePossuiDispositivos()

    # a resposta e montada ANTES do delete: depois do commit o objeto
    # esta expirado e ler qualquer atributo dele levanta excecao.
    resposta = AmbienteRead.model_validate(ambiente)
    repository.excluir(db, ambiente)

    return resposta
