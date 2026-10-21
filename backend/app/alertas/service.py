from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alertas.models import Alerta


def aplicar_evento(db: Session, codigo: str, conteudo: dict) -> Alerta | None:
    """Traduz um evento de alerta (vindo da fila q.alertas) para a tabela.

    abrir  -> cria o alerta, ou atualiza o que ja estava aberto
    fechar -> encerra o alerta aberto, se houver
    """
    chave = conteudo["chave"]
    agora = datetime.now(UTC)
    aberto = db.scalars(
        select(Alerta).where(
            Alerta.dispositivo_codigo == codigo,
            Alerta.chave == chave,
            Alerta.ativo.is_(True),
        )
    ).first()

    if conteudo["acao"] == "abrir":
        if aberto is None:
            aberto = Alerta(
                dispositivo_codigo=codigo,
                chave=chave,
                origem=conteudo.get("origem", "?"),
                severidade=conteudo["severidade"],
                mensagem=conteudo["mensagem"][:255],
                valor=conteudo.get("valor"),
            )
            db.add(aberto)
        else:
            aberto.severidade = conteudo["severidade"]
            aberto.mensagem = conteudo["mensagem"][:255]
            aberto.valor = conteudo.get("valor")
            aberto.atualizado_em = agora
    elif conteudo["acao"] == "fechar" and aberto is not None:
        aberto.ativo = False
        aberto.fechado_em = agora
        aberto.atualizado_em = agora

    db.commit()
    return aberto


def listar(db: Session, apenas_ativos: bool, limite: int, codigo: str | None) -> list[Alerta]:
    consulta = select(Alerta).order_by(Alerta.ativo.desc(), Alerta.atualizado_em.desc())
    if apenas_ativos:
        consulta = consulta.where(Alerta.ativo.is_(True))
    if codigo:
        consulta = consulta.where(Alerta.dispositivo_codigo == codigo)
    return list(db.scalars(consulta.limit(limite)).all())
