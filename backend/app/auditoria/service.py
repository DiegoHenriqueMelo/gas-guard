from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auditoria.models import Auditoria
from app.core.database import SessionLocal


def registrar(
    db: Session,
    acao: str,
    usuario: str | None = None,
    papel: str | None = None,
    detalhe: dict | None = None,
    ip: str | None = None,
    sucesso: bool = True,
) -> None:
    """Grava uma linha de auditoria e faz commit na hora.

    Commit separado de proposito: uma tentativa de login que falha precisa
    ficar registrada mesmo que o resto da request de errado.
    """
    db.add(
        Auditoria(
            acao=acao,
            usuario=usuario,
            papel=papel,
            detalhe=detalhe or {},
            ip=ip,
            sucesso=sucesso,
        )
    )
    db.commit()


def registrar_fora_de_request(acao: str, **campos) -> None:
    """Para quem nao esta numa request HTTP (consumidores de fila)."""
    with SessionLocal() as db:
        registrar(db, acao, **campos)


def listar(db: Session, limite: int, acao: str | None, usuario: str | None) -> list[Auditoria]:
    consulta = select(Auditoria).order_by(Auditoria.id.desc()).limit(limite)
    if acao:
        consulta = consulta.where(Auditoria.acao.startswith(acao))
    if usuario:
        consulta = consulta.where(Auditoria.usuario == usuario)
    return list(db.scalars(consulta).all())
