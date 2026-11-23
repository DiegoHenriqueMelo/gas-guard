from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

OPERADORES = (">", ">=", "<", "<=")


class Regra(Base):
    """Regra de negocio: "SE <sensor>.<campo> <operador> <limite> ENTAO <acao> no <alvo>".

    Ex.: SE GAS-01.ppm >= 2000 ENTAO fechar VALVULA-01.

    A regra dispara na TRANSICAO: quando a condicao passa de falsa para
    verdadeira. Enquanto o gas continua alto ela nao manda o mesmo comando
    de novo a cada leitura, e se o operador reabrir a valvula na mao, a regra
    so volta a agir quando o gas cair e subir outra vez.
    """

    __tablename__ = "regras"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    ativa: Mapped[bool] = mapped_column(default=True)

    dispositivo_codigo: Mapped[str] = mapped_column(
        ForeignKey("dispositivos.codigo", onupdate="CASCADE")
    )
    campo: Mapped[str] = mapped_column(String(30))
    operador: Mapped[str] = mapped_column(String(2))
    limite: Mapped[float]

    alvo_codigo: Mapped[str] = mapped_column(
        ForeignKey("dispositivos.codigo", onupdate="CASCADE")
    )
    acao: Mapped[str] = mapped_column(String(20))

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def avaliar(self, valor: float) -> bool:
        if self.operador == ">":
            return valor > self.limite
        if self.operador == ">=":
            return valor >= self.limite
        if self.operador == "<":
            return valor < self.limite
        return valor <= self.limite
