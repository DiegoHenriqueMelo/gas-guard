"""Dependencies de autenticacao para as rotas.

    @router.get(...)
    def rota(usuario: UsuarioToken = Depends(exige("operador"))): ...

Visualizador so ve. Operador tambem comanda atuadores e o simulador.
Administrador tambem gera dados, treina modelos, edita cadastros e ve a
auditoria. Cada papel herda o que os anteriores podem.
"""

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer

from app.auth.models import PAPEIS
from app.auth.schemas import UsuarioToken
from app.auth.seguranca import ler_token

# tokenUrl e a rota que o Swagger chama no botao Authorize (formulario).
# auto_error=False: quem decide o erro somos nos, com mensagem em portugues.
esquema = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

NIVEL = {papel: indice for indice, papel in enumerate(PAPEIS)}


def usuario_atual(token: str | None = Depends(esquema)) -> UsuarioToken:
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Faça login para continuar",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        conteudo = ler_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada, entre de novo")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

    return UsuarioToken(
        usuario=conteudo["sub"], papel=conteudo["papel"], nome=conteudo.get("nome", "")
    )


def exige(papel_minimo: str):
    """Fabrica de dependency: libera a rota a partir de um papel."""
    if papel_minimo not in NIVEL:
        raise ValueError(f"papel desconhecido: {papel_minimo}")

    def verificar(usuario: UsuarioToken = Depends(usuario_atual)) -> UsuarioToken:
        if NIVEL.get(usuario.papel, -1) < NIVEL[papel_minimo]:
            raise HTTPException(
                status_code=403,
                detail=f"Ação permitida a partir do papel {papel_minimo}",
            )
        return usuario

    return verificar


def ip_do_cliente(request: Request) -> str | None:
    """IP de quem chamou. A API so e alcancada pelo nginx do frontend, que
    repassa o IP real no X-Real-IP; o request.client seria o proprio nginx."""
    return request.headers.get("x-real-ip") or (
        request.client.host if request.client else None
    )
