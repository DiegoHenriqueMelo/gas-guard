from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auditoria.service import registrar
from app.auth.models import Usuario
from app.auth.seguranca import conferir_senha, criar_token, hash_senha
from app.core.limitador import Limitador

# Duas barreiras contra quem tenta adivinhar senha:
# 1) por CONTA: 5 erros seguidos travam aquele usuario por 5 minutos;
# 2) por IP: no maximo 10 tentativas por minuto, de qualquer usuario.
MAX_FALHAS = 5
BLOQUEIO = timedelta(minutes=5)
limitador_por_ip = Limitador(maximo=10, janela_segundos=60)

# Conferimos a senha contra este hash quando o usuario nao existe. Sem isso,
# "usuario inexistente" responderia instantaneamente e "senha errada"
# levaria 0,2 s do bcrypt: pelo tempo de resposta daria para descobrir
# quais usuarios existem.
_HASH_FALSO = hash_senha("senha-que-nao-existe")


class LoginRecusado(Exception):
    def __init__(self, motivo: str, status: int = 401):
        self.motivo = motivo
        self.status = status


def autenticar(db: Session, usuario: str, senha: str, ip: str | None) -> tuple[str, Usuario]:
    """Devolve (token, usuario) ou levanta LoginRecusado. Tudo vai para a auditoria."""
    permitido, espera = limitador_por_ip.permitir(ip or "?")
    if not permitido:
        registrar(db, "login.limitado", usuario=usuario, ip=ip, sucesso=False)
        raise LoginRecusado(
            f"Muitas tentativas. Tente de novo em {int(espera) + 1} s", status=429
        )

    conta = db.scalars(select(Usuario).where(Usuario.usuario == usuario)).first()
    agora = datetime.now(UTC)

    if conta is None or not conta.ativo:
        conferir_senha(senha, _HASH_FALSO)
        registrar(db, "login.falhou", usuario=usuario, ip=ip, sucesso=False)
        raise LoginRecusado("Usuário ou senha inválidos")

    if conta.bloqueado_ate and conta.bloqueado_ate > agora:
        registrar(db, "login.bloqueado", usuario=usuario, ip=ip, sucesso=False)
        minutos = int((conta.bloqueado_ate - agora).total_seconds() // 60) + 1
        raise LoginRecusado(
            f"Conta bloqueada por excesso de tentativas. Tente em {minutos} min",
            status=423,
        )

    if not conferir_senha(senha, conta.senha_hash):
        conta.tentativas_falhas += 1
        detalhe = {"tentativas": conta.tentativas_falhas}
        if conta.tentativas_falhas >= MAX_FALHAS:
            conta.bloqueado_ate = agora + BLOQUEIO
            conta.tentativas_falhas = 0
            detalhe["bloqueada_ate"] = conta.bloqueado_ate.isoformat()
        db.commit()
        registrar(db, "login.falhou", usuario=usuario, ip=ip, detalhe=detalhe, sucesso=False)
        raise LoginRecusado("Usuário ou senha inválidos")

    conta.tentativas_falhas = 0
    conta.bloqueado_ate = None
    conta.ultimo_login = agora
    db.commit()
    registrar(db, "login", usuario=conta.usuario, papel=conta.papel, ip=ip)

    return criar_token(conta.usuario, conta.papel, conta.nome), conta
