from app.core.influx import ler_ultimas_leituras
from app.leituras.schemas import LeituraOut


def historico(codigo: str, minutos: int) -> list[LeituraOut]:
    """Traduz as tuplas cruas do Influx para o formato da API."""
    registros = ler_ultimas_leituras(codigo, minutos)

    return [LeituraOut(horario=horario, ppm=ppm) for horario, ppm in registros]
