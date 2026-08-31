from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.core.influx import gravar_leitura
from app.dispositivos.repository import buscar_por_codigo, editar_dispositivo
from app.leituras.schemas import LeituraIn


def processar_leitura(leitura: LeituraIn) -> None:
    with SessionLocal() as db:
        dispositivo = buscar_por_codigo(db, leitura.codigo)

        if dispositivo is None:
            print(f"dispositivo desconhecido: {leitura.codigo}, leitura descartada")
            return

        gravar_leitura(leitura.codigo, leitura.ppm)

        agora = datetime.now(timezone.utc)
        editar_dispositivo(db, dispositivo, {"ultimo_contato": agora})
