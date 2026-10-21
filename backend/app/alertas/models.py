from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Alerta(Base):
    """Um alerta aberto (ativo) ou ja encerrado.

    `chave` diz QUE alerta e este para aquele dispositivo: "limite" (leitura
    fora da faixa), "ia_saude" (indice de saude baixo), "ia_rul" (falha
    prevista em breve), "falha" (o equipamento parou). So existe um alerta
    ativo por (dispositivo, chave): se a situacao piora, o mesmo registro
    sobe de severidade em vez de abrir outro.
    """

    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(primary_key=True)
    dispositivo_codigo: Mapped[str] = mapped_column(String(50), index=True)
    chave: Mapped[str] = mapped_column(String(30))
    origem: Mapped[str] = mapped_column(String(20))  # "regras" ou "ia"
    severidade: Mapped[str] = mapped_column(String(10))  # atencao | critico
    mensagem: Mapped[str] = mapped_column(String(255))
    valor: Mapped[float | None]
    ativo: Mapped[bool] = mapped_column(default=True, index=True)

    aberto_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fechado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
