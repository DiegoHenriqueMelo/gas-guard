from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import service
from app.auth.deps import ip_do_cliente, usuario_atual
from app.auth.schemas import LoginIn, LoginOut, TokenOAuth, UsuarioToken
from app.core.database import get_db

router = APIRouter(prefix="/api/auth", tags=["autenticação"])


def _entrar(db: Session, usuario: str, senha: str, request: Request):
    try:
        return service.autenticar(db, usuario, senha, ip_do_cliente(request))
    except service.LoginRecusado as recusa:
        raise HTTPException(status_code=recusa.status, detail=recusa.motivo)


@router.post("/login", response_model=LoginOut)
def login(dados: LoginIn, request: Request, db: Session = Depends(get_db)):
    """Login do frontend: JSON com usuario e senha, devolve o JWT."""
    token, conta = _entrar(db, dados.usuario, dados.senha, request)
    return LoginOut(
        token=token,
        usuario=UsuarioToken(usuario=conta.usuario, papel=conta.papel, nome=conta.nome),
    )


@router.post("/token", response_model=TokenOAuth, include_in_schema=False)
def token_swagger(
    request: Request,
    formulario: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """O mesmo login, no formato de formulario do OAuth2. E o que o botao
    Authorize da pagina /api/docs chama."""
    token, _ = _entrar(db, formulario.username, formulario.password, request)
    return TokenOAuth(access_token=token)


@router.get("/eu", response_model=UsuarioToken)
def quem_sou_eu(usuario: UsuarioToken = Depends(usuario_atual)):
    return usuario
