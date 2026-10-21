from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.ambientes.models import Ambiente


class Dispositivo(Base):
    """Tudo o que existe na cozinha e fala com o sistema.

    Tres categorias:
      sensor       -- so mede (gas, temperatura, umidade, luz, vazao)
      atuador      -- recebe comando (valvula, sirene)
      equipamento  -- maquina que se desgasta e e monitorada pela IA. O
                      exaustor e equipamento E atuador: liga e desliga por
                      comando, e tambem tem vibracao, corrente, temperatura
                      e rotacao medidas.
    """

    __tablename__ = "dispositivos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    nome: Mapped[str] = mapped_column(String(100), unique=True)
    ativo: Mapped[bool] = mapped_column(default=True)
    ultimo_contato: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    categoria: Mapped[str] = mapped_column(String(20), default="sensor")
    # gas, temperatura, umidade, luminosidade, vazao, exaustor, valvula, sirene
    tipo: Mapped[str] = mapped_column(String(30), default="gas")
    # O campo da leitura que define a cor do dispositivo (ppm, temperatura...)
    campo_principal: Mapped[str | None] = mapped_column(String(30))
    unidade: Mapped[str | None] = mapped_column(String(15))
    controlavel: Mapped[bool] = mapped_column(default=False)

    # Faixa normal do sensor. Dentro de [normal_min, normal_max] = normal;
    # fora dela mas dentro de [critico_min, critico_max] = atencao; fora das
    # duas = critico. Limite nulo = sem limite daquele lado.
    normal_min: Mapped[float | None]
    normal_max: Mapped[float | None]
    critico_min: Mapped[float | None]
    critico_max: Mapped[float | None]

    # a COLUNA que existe no banco (guarda o numero)
    ambiente_id: Mapped[int] = mapped_column(ForeignKey("ambientes.id"))

    # a NAVEGACAO que so existe no Python (devolve o objeto)
    ambiente: Mapped["Ambiente"] = relationship(back_populates="dispositivos")

    def classificar(self, valor: float | None) -> str:
        """normal, atencao ou critico, pela faixa cadastrada."""
        if valor is None:
            return "sem_dados"
        if self.critico_min is not None and valor < self.critico_min:
            return "critico"
        if self.critico_max is not None and valor >= self.critico_max:
            return "critico"
        if self.normal_min is not None and valor < self.normal_min:
            return "atencao"
        if self.normal_max is not None and valor >= self.normal_max:
            return "atencao"
        return "normal"
