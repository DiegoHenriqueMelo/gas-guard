from sqlalchemy.orm import Session

from app.dispositivos import repository
from app.dispositivos.catalogo import ACOES_POR_TIPO, TIPOS
from app.dispositivos.exceptions import (
    AmbienteNaoEncontrado,
    CodigoJaCadastrado,
    ComandoInvalido,
    DispositivoNaoEncontrado,
    NomeJaCadastrado,
)
from app.dispositivos.models import Dispositivo
from app.dispositivos.schemas import DispositivoCreate, DispositivoUpdate
from app.mensageria import envelope, topologia


def criar_dispositivo(db: Session, dados: DispositivoCreate) -> Dispositivo:
    codigo_exist = repository.buscar_por_codigo(db, dados.codigo)

    if codigo_exist is not None:
        raise CodigoJaCadastrado()

    if repository.nome_valido(db, dados.nome) is not None:
        raise NomeJaCadastrado()

    ambiente_exist = repository.buscar_ambiente(db, dados.ambiente_id)

    if ambiente_exist is None:
        raise AmbienteNaoEncontrado()

    # o que nao veio no corpo sai do catalogo do tipo
    padrao = TIPOS[dados.tipo]

    dispositivo = Dispositivo(
        codigo=dados.codigo,
        nome=dados.nome,
        ambiente_id=dados.ambiente_id,
        tipo=dados.tipo,
        categoria=dados.categoria or padrao["categoria"],
        campo_principal=dados.campo_principal or padrao["campo"],
        unidade=dados.unidade or padrao["unidade"],
        controlavel=(
            dados.controlavel
            if dados.controlavel is not None
            else dados.tipo in ACOES_POR_TIPO
        ),
        normal_min=dados.normal_min,
        normal_max=dados.normal_max,
        critico_min=dados.critico_min,
        critico_max=dados.critico_max,
    )

    return repository.salvar(db, dispositivo)


def listar_dispositivos(db: Session) -> list[Dispositivo]:
    return repository.listar_dispositivos(db)


def buscar_por_codigo(codigo: str, db: Session) -> Dispositivo:
    dispositivo = repository.buscar_por_codigo(db, codigo)

    if dispositivo is None:
        raise DispositivoNaoEncontrado()

    return dispositivo


def editar_dispositivo(codigo: str, dados: DispositivoUpdate, db: Session) -> Dispositivo:
    dispositivo = repository.buscar_por_codigo(db, codigo)

    if dispositivo is None:
        raise DispositivoNaoEncontrado()

    # so os campos que o cliente REALMENTE mandou no corpo
    campos = dados.model_dump(exclude_unset=True)

    if "ambiente_id" in campos:
        ambiente = repository.buscar_ambiente(db, campos["ambiente_id"])
        if ambiente is None:
            raise AmbienteNaoEncontrado()

    if "nome" in campos:
        outro = repository.nome_valido(db, campos["nome"])
        if outro is not None and outro.id != dispositivo.id:
            raise NomeJaCadastrado()

    return repository.editar_dispositivo(db, dispositivo, campos)


def excluir_dispositivo(codigo: str, db: Session) -> Dispositivo:
    dispositivo = repository.buscar_por_codigo(db, codigo)

    if dispositivo is None:
        raise DispositivoNaoEncontrado()

    return repository.excluir_dispositivo(dispositivo, db)


def montar_comando(
    dispositivo: Dispositivo, acao: str, origem: str, usuario: str | None
) -> tuple[str, envelope.Envelope]:
    """Valida e monta o comando. Devolve (routing_key, envelope).

    Usado pelas DUAS portas que mandam comando: o botao do painel (API) e a
    regra automatica (servico regras). A validacao fica num lugar so.
    """
    if not dispositivo.ativo:
        raise ComandoInvalido("Dispositivo desativado")
    if not dispositivo.controlavel:
        raise ComandoInvalido("Este dispositivo não aceita comandos")

    permitidas = ACOES_POR_TIPO.get(dispositivo.tipo, ())
    if acao not in permitidas:
        raise ComandoInvalido(
            f"Ação inválida para {dispositivo.tipo}; use: {', '.join(permitidas)}"
        )

    zona = dispositivo.ambiente.zona
    rk = topologia.rk_comando(zona, dispositivo.tipo, dispositivo.codigo)
    mensagem = envelope.novo(
        "comando",
        dispositivo.codigo,
        {
            "zona": zona,
            "tipo": dispositivo.tipo,
            "acao": acao,
            "parametros": {},
            "origem": origem,
            "usuario": usuario,
        },
    )
    return rk, mensagem
