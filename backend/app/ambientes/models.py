from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.dispositivos.models import Dispositivo


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
