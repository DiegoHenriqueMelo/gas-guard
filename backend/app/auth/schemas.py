from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    usuario: str = Field(min_length=1, max_length=50)
    senha: str = Field(min_length=1, max_length=72)


class UsuarioToken(BaseModel):
    """O que vem dentro do JWT. Usado como "usuario logado" nas rotas."""

    usuario: str
    papel: str
    nome: str


class UsuarioRead(BaseModel):
    id: int
    usuario: str
    nome: str
    papel: str
    ativo: bool
    ultimo_login: datetime | None

    model_config = ConfigDict(from_attributes=True)


class LoginOut(BaseModel):
    token: str
    usuario: UsuarioToken


class TokenOAuth(BaseModel):
    """Formato que o botao Authorize do Swagger espera."""

    access_token: str
    token_type: str = "bearer"
