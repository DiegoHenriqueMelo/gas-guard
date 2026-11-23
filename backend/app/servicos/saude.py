"""Healthcheck dos servicos de fundo: `python -m app.servicos.saude`.

Sai com 0 se o batimento foi tocado nos ultimos 30 segundos, 1 caso
contrario. O docker-compose usa a saida para marcar o container como
healthy ou unhealthy.
"""

import sys
import time

from app.servicos.base import ARQUIVO_BATIMENTO

LIMITE_SEGUNDOS = 30

try:
    idade = time.time() - ARQUIVO_BATIMENTO.stat().st_mtime
except FileNotFoundError:
    sys.exit(1)

sys.exit(0 if idade < LIMITE_SEGUNDOS else 1)
