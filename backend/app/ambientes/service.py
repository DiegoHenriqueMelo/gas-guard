from sqlalchemy.orm import Session

from app.ambientes import repository
from app.ambientes.exceptions import NomeJaCadastrado
from app.ambientes.models import Ambiente
from app.ambientes.schemas import AmbienteCreate


def criar_ambiente(db: Session, dados: AmbienteCreate) -> Ambiente:
    if repository.buscar_por_nome(db, dados.nome) is not None:
        raise NomeJaCadastrado()

    ambiente = Ambiente(
        nome=dados.nome,
        descricao=dados.descricao,
    )

    return repository.salvar(db, ambiente)
