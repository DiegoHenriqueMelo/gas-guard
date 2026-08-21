from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Ambiente(Base):
    """Local monitorado: cozinha, laboratorio, deposito..."""

    __tablename__ = "ambientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), unique=True)
    descricao: Mapped[str | None] = mapped_column(String(255))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # lado "um": um ambiente tem varios dispositivos
    dispositivos: Mapped[list["Dispositivo"]] = relationship(
        back_populates="ambiente"
    )


class Dispositivo(Base):
    """Sensor que vai ficar no local para detectar vazamento"""

    __tablename__ = "dispositivos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    nome: Mapped[str] = mapped_column(String(100), unique=True)
    ativo: Mapped[bool] = mapped_column(default=True)
    ultimo_contato: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # a COLUNA que existe no banco (guarda o numero)
    ambiente_id: Mapped[int] = mapped_column(ForeignKey("ambientes.id"))

    # a NAVEGACAO que so existe no Python (devolve o objeto)
    ambiente: Mapped["Ambiente"] = relationship(back_populates="dispositivos")
