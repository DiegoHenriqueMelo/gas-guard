from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.auditoria.service import registrar
from app.auth.deps import exige, ip_do_cliente, usuario_atual
from app.auth.schemas import UsuarioToken
from app.core.database import SessionLocal, get_db
from app.dispositivos import service
from app.dispositivos.exceptions import (
    AmbienteNaoEncontrado,
    CodigoJaCadastrado,
    ComandoInvalido,
    DispositivoNaoEncontrado,
    NomeJaCadastrado,
)
from app.dispositivos.schemas import (
    ComandoIn,
    ComandoOut,
    DispositivoCreate,
    DispositivoRead,
    DispositivoUpdate,
)
from app.mensageria import topologia
from app.tempo_real.barramento import barramento

# Ler: qualquer usuario logado. Cadastro: administrador. Comando: operador.
router = APIRouter(
    prefix="/api/dispositivos", tags=["dispositivos"], dependencies=[Depends(usuario_atual)]
)


@router.post("", response_model=DispositivoRead, status_code=201)
def criar_dispositivo(
    dados: DispositivoCreate,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    try:
        dispositivo = service.criar_dispositivo(db, dados)
    except CodigoJaCadastrado:
        raise HTTPException(status_code=409, detail="Código já cadastrado")
    except NomeJaCadastrado:
        raise HTTPException(status_code=409, detail="Nome já cadastrado")
    except AmbienteNaoEncontrado:
        raise HTTPException(status_code=400, detail="Ambiente não encontrado")

    registrar(
        db, "dispositivo.criado", usuario.usuario, usuario.papel,
        {"codigo": dispositivo.codigo, "tipo": dispositivo.tipo}, ip_do_cliente(request),
    )
    return dispositivo


@router.get("", response_model=list[DispositivoRead])
def listar_dispositivos(db: Session = Depends(get_db)):
    return service.listar_dispositivos(db)


@router.get("/{codigo}", response_model=DispositivoRead)
def buscar_por_codigo(codigo: str, db: Session = Depends(get_db)):
    try:
        return service.buscar_por_codigo(codigo, db)
    except DispositivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")


@router.patch("/{codigo}", response_model=DispositivoRead)
def editar_dispositivo(
    codigo: str,
    dados: DispositivoUpdate,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    try:
        dispositivo = service.editar_dispositivo(codigo, dados, db)
    except DispositivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    except AmbienteNaoEncontrado:
        raise HTTPException(status_code=400, detail="Ambiente não encontrado")
    except NomeJaCadastrado:
        raise HTTPException(status_code=409, detail="Nome já cadastrado")

    registrar(
        db, "dispositivo.editado", usuario.usuario, usuario.papel,
        {"codigo": codigo, "campos": dados.model_dump(exclude_unset=True)},
        ip_do_cliente(request),
    )
    return dispositivo


@router.delete("/{codigo}", response_model=DispositivoRead)
def excluir_dispositivo(
    codigo: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: UsuarioToken = Depends(exige("administrador")),
):
    try:
        dispositivo = service.excluir_dispositivo(codigo, db)
    except DispositivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")

    registrar(
        db, "dispositivo.desativado", usuario.usuario, usuario.papel,
        {"codigo": codigo}, ip_do_cliente(request),
    )
    return dispositivo


@router.post("/{codigo}/comandos", response_model=ComandoOut, status_code=202)
async def enviar_comando(
    codigo: str,
    dados: ComandoIn,
    request: Request,
    usuario: UsuarioToken = Depends(exige("operador")),
):
    """Web -> IoT: o botao do painel vira mensagem no RabbitMQ.

    202 Accepted, e nao 200: a API so garante que o comando entrou no
    barramento. Quem confirma que a valvula fechou e a PROXIMA leitura do
    simulador, que chega pelo WebSocket com o estado novo.
    """
    ip = ip_do_cliente(request)

    # A parte de banco e sincrona; roda numa thread para nao travar o loop
    # do asyncio, que e quem atende o WebSocket.
    def preparar():
        with SessionLocal() as db:
            dispositivo = service.buscar_por_codigo(codigo, db)
            rk, mensagem = service.montar_comando(
                dispositivo, dados.acao, origem="web", usuario=usuario.usuario
            )
            registrar(
                db, "comando.enviado", usuario.usuario, usuario.papel,
                {"dispositivo": codigo, "acao": dados.acao, "id": mensagem.id}, ip,
            )
            return rk, mensagem

    try:
        rk, mensagem = await run_in_threadpool(preparar)
    except DispositivoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    except ComandoInvalido as erro:
        raise HTTPException(status_code=422, detail=erro.motivo)

    await barramento.publicar(topologia.EX_COMANDOS, rk, mensagem)
    return ComandoOut(id=mensagem.id, dispositivo=codigo, acao=dados.acao, routing_key=rk)
