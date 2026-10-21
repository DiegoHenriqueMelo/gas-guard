"""Hash de senha (bcrypt) e token de acesso (JWT)."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core import config

ALGORITMO = "HS256"

# O bcrypt so olha os primeiros 72 bytes da senha; a versao 5 da biblioteca
# passou a recusar senha maior em vez de cortar calada. Limitamos na entrada.
MAX_BYTES_SENHA = 72


def hash_senha(senha: str) -> str:
    """O sal aleatorio vai embutido no proprio hash: "$2b$12$<sal><hash>".

    12 rodadas = 2^12 iteracoes. Lento de proposito (~0,2 s): e o que torna
    inviavel testar milhoes de senhas se o banco vazar.
    """
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt(rounds=12)).decode()


def conferir_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), senha_hash.encode())
    except ValueError:
        return False


def _segredo() -> str:
    return config.obrigatoria("JWT_SEGREDO")


def criar_token(usuario: str, papel: str, nome: str) -> str:
    agora = datetime.now(UTC)
    conteudo = {
        "sub": usuario,
        "papel": papel,
        "nome": nome,
        "iat": agora,
        "exp": agora + timedelta(minutes=config.JWT_MINUTOS),
    }
    return jwt.encode(conteudo, _segredo(), algorithm=ALGORITMO)


def ler_token(token: str) -> dict:
    """Valida assinatura e validade. Levanta jwt.PyJWTError se nao bater.

    `algorithms` e uma lista fechada de proposito: sem ela, um token forjado
    com "alg": "none" passaria.
    """
    return jwt.decode(token, _segredo(), algorithms=[ALGORITMO])
