"""Regras: o atuador automatico e o dono da tabela de alertas.

Consome duas filas:

q.regras (toda a telemetria)
  1. Regras de negocio cadastradas no Postgres, por exemplo
     "GAS-01.ppm >= 2000 -> fechar VALVULA-01". A regra dispara na
     TRANSICAO (falso -> verdadeiro) e so manda o comando se o atuador
     ainda nao estiver no estado desejado. O comando sai pelo mesmo caminho
     do botao do painel: gg.comandos -> gateway -> MQTT -> simulador.
  2. Alertas de faixa: leitura fora da faixa normal do cadastro abre um
     alerta (com histerese), que e publicado em alerta.#.

q.alertas (alerta.# de qualquer origem: daqui e da inferencia)
  Grava abertura e fechamento na tabela `alertas`. Todo alerta passa por
  esta fila, entao so existe um lugar que escreve na tabela.
"""

import asyncio
import time
from collections import defaultdict

import app.core.tabelas  # noqa: F401  (registra todos os models)
from app.alertas.histerese import Histerese
from app.alertas.models import Alerta
from app.alertas.service import aplicar_evento
from app.auditoria.service import registrar_fora_de_request
from app.core.database import SessionLocal
from app.dispositivos.catalogo import ESTADO_DEPOIS_DA_ACAO
from app.dispositivos.exceptions import ComandoInvalido
from app.dispositivos.models import Dispositivo
from app.dispositivos.repository import listar_com_ambiente
from app.dispositivos.service import montar_comando
from app.mensageria import envelope, topologia
from app.mensageria.conexao import Publicador, conectar, consumir
from app.regras.models import Regra
from app.servicos.base import batimento, configurar_log, rodar

log = configurar_log("regras")

RECARREGAR = 10  # segundos entre releituras de regras e cadastro

ROTULO_SEVERIDADE = {"atencao": "atenção", "critico": "crítico"}


class Memoria:
    """Cadastro e regras em cache, mais o que ja se sabe dos atuadores."""

    def __init__(self) -> None:
        self.dispositivos: dict[str, Dispositivo] = {}
        self.regras_por_origem: dict[str, list[Regra]] = defaultdict(list)
        self.lido_em = 0.0
        # ultimo estado conhecido de cada atuador ("aberta", "ligado"...)
        self.estados: dict[str, str] = {}
        # resultado da ultima avaliacao de cada regra (para achar a transicao)
        self.ultima_condicao: dict[int, bool] = {}
        # uma histerese por dispositivo para o alerta de faixa
        self.histereses: dict[str, Histerese] = defaultdict(
            lambda: Histerese(n_abrir=2, n_fechar=5)
        )
        self.retomou_alertas = False

    def _ler(self):
        with SessionLocal() as db:
            dispositivos = {d.codigo: d for d in listar_com_ambiente(db)}
            regras = db.query(Regra).filter(Regra.ativa.is_(True)).all()
            abertos = [
                (a.dispositivo_codigo, a.chave, a.severidade)
                for a in db.query(Alerta).filter(Alerta.ativo.is_(True), Alerta.origem == "regras")
            ]
        # Fora da sessao os objetos ficam "desanexados", mas o que ja foi
        # carregado (inclusive o ambiente, pelo joinedload) continua legivel.
        return dispositivos, regras, abertos

    def retomar_alertas(self, abertos) -> None:
        """A histerese vive na memoria. Se o servico reinicia com um alerta
        aberto no banco, ele precisa lembrar disso - senao nunca mandaria o
        "fechar" quando a situacao se resolvesse."""
        for codigo, chave, severidade in abertos:
            if chave == "limite":
                self.histereses[codigo].ativo = severidade
            elif chave == "falha":
                self.histereses[f"{codigo}:falha"].ativo = "critico"
        self.retomou_alertas = True

    async def atualizar_se_preciso(self) -> None:
        if time.monotonic() - self.lido_em < RECARREGAR:
            return
        try:
            dispositivos, regras, abertos = await asyncio.to_thread(self._ler)
        except Exception:
            log.exception("nao consegui reler regras e cadastro; mantendo os anteriores")
            return
        if not self.retomou_alertas:
            self.retomar_alertas(abertos)
        self.dispositivos = dispositivos
        self.regras_por_origem = defaultdict(list)
        for regra in regras:
            self.regras_por_origem[regra.dispositivo_codigo].append(regra)
        self.lido_em = time.monotonic()


async def principal(parar: asyncio.Event) -> None:
    conexao = await conectar("regras")
    canal = await conexao.channel()
    await canal.set_qos(prefetch_count=50)
    publicador = Publicador(canal)
    memoria = Memoria()

    async def publicar_alerta(dispositivo: Dispositivo, conteudo: dict) -> None:
        zona = dispositivo.ambiente.zona
        conteudo = {"zona": zona, "tipo": dispositivo.tipo, "origem": "regras", **conteudo}
        rk = topologia.rk("alerta", zona, dispositivo.tipo, dispositivo.codigo)
        await publicador.publicar(
            topologia.EX_EVENTOS, rk, envelope.novo("alerta", dispositivo.codigo, conteudo)
        )

    async def verificar_faixa(dispositivo: Dispositivo, leituras: dict, estado: str | None):
        # equipamento que parou sozinho e alerta critico na hora, sem histerese
        if dispositivo.categoria == "equipamento":
            falhou = estado == "falha"
            histerese = memoria.histereses[f"{dispositivo.codigo}:falha"]
            if falhou and histerese.ativo is None:
                histerese.ativo = "critico"
                await publicar_alerta(dispositivo, {
                    "chave": "falha", "acao": "abrir", "severidade": "critico",
                    "mensagem": f"{dispositivo.nome} parou por falha", "valor": None,
                })
            elif not falhou and histerese.ativo is not None:
                histerese.ativo = None
                await publicar_alerta(dispositivo, {"chave": "falha", "acao": "fechar"})

        campo = dispositivo.campo_principal
        if not campo or campo not in leituras:
            return
        valor = leituras[campo]
        nivel = dispositivo.classificar(valor)
        severidade = None if nivel == "normal" else nivel
        mudanca = memoria.histereses[dispositivo.codigo].avaliar(severidade)
        if mudanca is None:
            return

        acao, severidade = mudanca
        if acao == "abrir":
            mensagem = (
                f"{dispositivo.nome} em nível {ROTULO_SEVERIDADE[severidade]}: "
                f"{valor:.1f} {dispositivo.unidade or ''}".strip()
            )
            await publicar_alerta(dispositivo, {
                "chave": "limite", "acao": "abrir", "severidade": severidade,
                "mensagem": mensagem, "valor": valor,
            })
        else:
            await publicar_alerta(dispositivo, {"chave": "limite", "acao": "fechar"})

    async def disparar(regra: Regra, valor: float) -> None:
        alvo = memoria.dispositivos.get(regra.alvo_codigo)
        if alvo is None:
            log.warning("regra %s aponta para %s, que nao existe", regra.id, regra.alvo_codigo)
            return

        desejado = ESTADO_DEPOIS_DA_ACAO.get(regra.acao)
        if desejado and memoria.estados.get(alvo.codigo) == desejado:
            log.info("regra '%s': %s ja esta %s", regra.nome, alvo.codigo, desejado)
            return

        try:
            rk, comando = montar_comando(alvo, regra.acao, origem=f"regra:{regra.id}", usuario=None)
        except ComandoInvalido as erro:
            log.warning("regra '%s' nao pode agir: %s", regra.nome, erro.motivo)
            return

        await publicador.publicar(topologia.EX_COMANDOS, rk, comando)

        detalhe = {
            "regra_id": regra.id,
            "regra": regra.nome,
            "gatilho": regra.dispositivo_codigo,
            "campo": regra.campo,
            "valor": round(valor, 2),
            "condicao": f"{regra.operador} {regra.limite:g}",
            "alvo": alvo.codigo,
            "acao": regra.acao,
            "comando_id": comando.id,
        }
        zona = alvo.ambiente.zona
        await publicador.publicar(
            topologia.EX_EVENTOS,
            topologia.rk("acionamento", zona, alvo.tipo, alvo.codigo),
            envelope.novo("acionamento", alvo.codigo, {"zona": zona, **detalhe}),
        )
        await asyncio.to_thread(registrar_fora_de_request, "comando.regra", detalhe=detalhe)
        log.info("regra '%s' disparou: %s %s (valor %.1f)", regra.nome, regra.acao, alvo.codigo, valor)

    async def ao_receber_telemetria(mensagem: envelope.Envelope, _bruta) -> None:
        await memoria.atualizar_se_preciso()
        codigo = mensagem.dispositivo
        dispositivo = memoria.dispositivos.get(codigo or "")
        if dispositivo is None:
            return  # o gateway ja barra desconhecidos; aqui so por garantia

        leituras = mensagem.conteudo.get("leituras") or {}
        estado = mensagem.conteudo.get("estado")
        if estado:
            memoria.estados[dispositivo.codigo] = estado

        await verificar_faixa(dispositivo, leituras, estado)

        for regra in memoria.regras_por_origem.get(dispositivo.codigo, []):
            valor = leituras.get(regra.campo)
            if valor is None:
                continue
            # Logo que o servico sobe, ainda nao chegou nenhuma leitura do
            # atuador. Espera conhecer o estado dele (chega em ate 2 s) antes
            # de avaliar, senao a primeira leitura sempre "dispara" a regra.
            if regra.alvo_codigo not in memoria.estados:
                continue
            agora = regra.avaliar(valor)
            antes = memoria.ultima_condicao.get(regra.id, False)
            memoria.ultima_condicao[regra.id] = agora
            if agora and not antes:
                await disparar(regra, valor)

    async def ao_receber_alerta(mensagem: envelope.Envelope, _bruta) -> None:
        conteudo = mensagem.conteudo
        if conteudo.get("acao") not in ("abrir", "fechar") or not conteudo.get("chave"):
            raise envelope.MensagemInvalida("alerta sem acao/chave")
        if conteudo["acao"] == "abrir" and not (
            conteudo.get("severidade") in ("atencao", "critico") and conteudo.get("mensagem")
        ):
            raise envelope.MensagemInvalida("alerta aberto sem severidade/mensagem")
        if not mensagem.dispositivo:
            raise envelope.MensagemInvalida("alerta sem dispositivo")

        def gravar():
            with SessionLocal() as db:
                aplicar_evento(db, mensagem.dispositivo, conteudo)

        await asyncio.to_thread(gravar)

    await consumir(canal, topologia.Q_REGRAS, ao_receber_telemetria, tipo_esperado="telemetria")
    await consumir(canal, topologia.Q_ALERTAS, ao_receber_alerta, tipo_esperado="alerta")

    tarefa = asyncio.create_task(batimento(lambda: not conexao.is_closed))
    await parar.wait()
    tarefa.cancel()
    await conexao.close()


if __name__ == "__main__":
    rodar(principal)
