from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.ambientes.models import Ambiente


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
