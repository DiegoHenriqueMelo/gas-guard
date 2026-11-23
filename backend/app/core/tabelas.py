"""Importa todos os models de uma vez.

O SQLAlchemy so conhece uma tabela depois que o modulo dela foi importado.
Quem precisa do conjunto completo (Alembic, seed, servicos de fundo) importa
este modulo e pronto. NAO remova nada daqui: model que falta faz o
autogenerate do Alembic gerar um DROP TABLE.
"""

from app.alertas.models import Alerta  # noqa: F401
from app.ambientes.models import Ambiente  # noqa: F401
from app.auditoria.models import Auditoria  # noqa: F401
from app.auth.models import Usuario  # noqa: F401
from app.dispositivos.models import Dispositivo  # noqa: F401
from app.ia.models import Configuracao, Modelo  # noqa: F401
from app.lab.models import Job  # noqa: F401
from app.regras.models import Regra  # noqa: F401
