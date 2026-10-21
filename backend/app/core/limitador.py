"""Limite de chamadas por chave numa janela de tempo (janela deslizante).

Fica em memoria, dentro do processo da API. Serve aqui porque a API roda
com um processo so; com varias replicas o contador teria de ir para um
lugar compartilhado (Redis, por exemplo).
"""

import threading
import time
from collections import defaultdict, deque


class Limitador:
    def __init__(self, maximo: int, janela_segundos: float):
        self.maximo = maximo
        self.janela = janela_segundos
        self._chamadas: dict[str, deque[float]] = defaultdict(deque)
        # as rotas sincronas do FastAPI rodam em threads diferentes
        self._trava = threading.Lock()

    def permitir(self, chave: str) -> tuple[bool, float]:
        """Registra a chamada se couber. Devolve (permitido, segundos ate liberar)."""
        agora = time.monotonic()
        with self._trava:
            fila = self._chamadas[chave]
            while fila and agora - fila[0] > self.janela:
                fila.popleft()

            if len(fila) >= self.maximo:
                return False, self.janela - (agora - fila[0])

            fila.append(agora)
            return True, 0.0
