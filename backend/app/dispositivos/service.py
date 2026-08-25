from sqlalchemy.orm import Session

from app.dispositivos import repository
from app.dispositivos.exceptions import AmbienteNaoEncontrado, CodigoJaCadastrado
from app.dispositivos.models import Dispositivo
from app.dispositivos.schemas import DispositivoCreate


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
