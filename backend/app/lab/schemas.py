from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from comum.fisica import AMOSTRAS_POR_DIA, CANAIS, MODOS_FALHA

TIPOS_AMBIENTE = ("gas", "temperatura", "umidade", "luminosidade")


class SensoresAmbiente(BaseModel):
    gas: int = Field(default=2, ge=0, le=50)
    temperatura: int = Field(default=2, ge=0, le=50)
    umidade: int = Field(default=2, ge=0, le=50)
    luminosidade: int = Field(default=2, ge=0, le=50)


class ParametrosGeracao(BaseModel):
    """O que a pagina Laboratorio de Dados deixa configurar."""

    equipamentos: int = Field(default=120, ge=10, le=500)
    sensores_ambiente: SensoresAmbiente = Field(default_factory=SensoresAmbiente)
    dias: int = Field(default=60, ge=1, le=365)
    pct_falha: float = Field(default=50.0, ge=0, le=100)
    modos: list[str] = Field(
        default_factory=lambda: ["rolamento", "desbalanceamento", "entupimento", "superaquecimento",
                                 "deriva_sensor", "travamento_sensor"]
    )
    ruido: float = Field(default=0.3, ge=0, le=1)
    pct_faltantes: float = Field(default=1.0, ge=0, le=20)
    pct_outliers: float = Field(default=0.5, ge=0, le=10)
    semente: int = Field(default=42, ge=0, le=2**31 - 1)
    amostra_influx: bool = True

    @model_validator(mode="after")
    def conferir(self):
        desconhecidos = set(self.modos) - set(MODOS_FALHA)
        if desconhecidos:
            raise ValueError(f"modos desconhecidos: {sorted(desconhecidos)}")
        if self.pct_falha > 0 and not self.modos:
            raise ValueError("escolha ao menos um modo de falha (ou 0% de falhas)")
        return self

    def leituras_estimadas(self) -> int:
        """Teto superior: maquinas que falham param antes do fim do periodo."""
        amostras = self.dias * AMOSTRAS_POR_DIA
        sensores = sum(self.sensores_ambiente.model_dump().values())
        return amostras * (self.equipamentos * len(CANAIS) + sensores)


class ParametrosTreino(BaseModel):
    dataset_job_id: int
    # Linhas vizinhas da mesma maquina sao quase iguais; amostrar uma a cada
    # N perde pouca informacao e deixa o treino caber na memoria.
    max_linhas: int = Field(default=400_000, ge=10_000, le=3_000_000)


class JobRead(BaseModel):
    id: int
    tipo: str
    status: str
    parametros: dict[str, Any]
    progresso: float
    etapa: str | None
    resultado: dict[str, Any] | None
    erro: str | None
    usuario: str | None
    criado_em: datetime
    iniciado_em: datetime | None
    concluido_em: datetime | None

    model_config = ConfigDict(from_attributes=True)
