from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.influx import gravar_leitura
from app.dispositivos.exceptions import DispositivoNaoEncontrado
from app.dispositivos.repository import buscar_por_codigo, editar_dispositivo
from app.leituras import repository
from app.leituras.schemas import LeituraIn, LeituraOut


def processar_leitura(leitura: LeituraIn) -> None:
    """Chamado pelo callback do MQTT, fora de qualquer request HTTP.

    Por isso a sessao e aberta aqui na mao: o get_db() do FastAPI so
    funciona dentro de uma request, e a Session nao e thread-safe.
    """
    with SessionLocal() as db:
        dispositivo = buscar_por_codigo(db, leitura.codigo)

        if dispositivo is None:
            print(f"dispositivo desconhecido: {leitura.codigo}, leitura descartada")
            return

        gravar_leitura(leitura.codigo, leitura.ppm)

        agora = datetime.now(timezone.utc)
        editar_dispositivo(db, dispositivo, {"ultimo_contato": agora})


def listar_historico(db: Session, codigo: str, minutos: int) -> list[LeituraOut]:
    # confere no Postgres ANTES de consultar o Influx: alem de devolver 404
    # decente, impede que um codigo arbitrario chegue na query Flux.
    if buscar_por_codigo(db, codigo) is None:
        raise DispositivoNaoEncontrado()

    return repository.historico(codigo, minutos)
