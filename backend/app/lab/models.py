from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Job(Base):
    """Um trabalho demorado: gerar dados sinteticos ou treinar modelos.

    A API cria o registro (na_fila) e publica na fila do RabbitMQ; o servico
    lab pega da fila, atualiza progresso e etapa, e no fim grava resultado
    ou erro. A interface acompanha pelo WebSocket.
    """

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(10))  # gerar | treinar
    # na_fila -> executando -> concluido | falhou
    status: Mapped[str] = mapped_column(String(12), default="na_fila", index=True)
    parametros: Mapped[dict] = mapped_column(JSONB, default=dict)
    progresso: Mapped[float] = mapped_column(default=0.0)
    etapa: Mapped[str | None] = mapped_column(String(120))
    resultado: Mapped[dict | None] = mapped_column(JSONB)
    erro: Mapped[str | None] = mapped_column(Text)
    usuario: Mapped[str | None] = mapped_column(String(50))

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    iniciado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
