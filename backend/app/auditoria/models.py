from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Auditoria(Base):
    """Quem fez o que, e quando. So recebe INSERT: nada aqui e editado.

    Exemplos de acao: login, login.falhou, comando.enviado, comando.regra,
    job.gerar, job.treinar, modelo.ativado, assistente.pergunta,
    dispositivo.criado...
    """

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    instante: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # nulo quando quem agiu foi o proprio sistema (uma regra, por exemplo)
    usuario: Mapped[str | None] = mapped_column(String(50), index=True)
    papel: Mapped[str | None] = mapped_column(String(20))
    acao: Mapped[str] = mapped_column(String(60), index=True)
    detalhe: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip: Mapped[str | None] = mapped_column(String(45))
    sucesso: Mapped[bool] = mapped_column(default=True)
