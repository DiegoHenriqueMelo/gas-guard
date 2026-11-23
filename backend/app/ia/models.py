from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Modelo(Base):
    """Uma versao treinada do par de modelos (saude + vida util).

    O arquivo com os modelos fica no volume /modelos; aqui ficam so os
    metadados e as metricas, para a pagina de Treinamento. So uma versao
    tem ativo = True: e a que o servico de inferencia usa.
    """

    __tablename__ = "modelos"

    id: Mapped[int] = mapped_column(primary_key=True)
    versao: Mapped[str] = mapped_column(String(20), unique=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    dataset_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    caminho: Mapped[str] = mapped_column(String(255))
    metricas: Mapped[dict] = mapped_column(JSONB, default=dict)
    # So entra em uso automaticamente se vencer a base simples nos DOIS alvos.
    venceu_base: Mapped[bool] = mapped_column(default=False)
    ativo: Mapped[bool] = mapped_column(default=False, index=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Configuracao(Base):
    """Parametros ajustaveis sem mexer no codigo (limites da IA, histerese)."""

    __tablename__ = "configuracoes"

    chave: Mapped[str] = mapped_column(String(50), primary_key=True)
    valor: Mapped[float]
    descricao: Mapped[str] = mapped_column(String(255))
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
