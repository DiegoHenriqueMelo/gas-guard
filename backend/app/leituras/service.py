from sqlalchemy.orm import Session

from app.core import influx
from app.dispositivos.exceptions import DispositivoNaoEncontrado
from app.dispositivos.repository import buscar_por_codigo


def listar_historico(
    db: Session, codigo: str, minutos: int, medida: str = influx.MEDIDA_TELEMETRIA
) -> list[dict]:
    # confere no Postgres ANTES de consultar o Influx: alem de devolver 404
    # decente, impede que um codigo arbitrario chegue na query Flux.
    if buscar_por_codigo(db, codigo) is None:
        raise DispositivoNaoEncontrado()

    return influx.historico(codigo, minutos, medida)
