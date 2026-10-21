"""O resumo dos dados que vai pronto no prompt do LLM.

Modelos pequenos (3 bilhoes de parametros) erram muito quando precisam
decidir sozinhos qual ferramenta chamar. Entao o LLM NAO consulta nada: o
backend monta um texto curto com o estado atual, as previsoes, os alertas e
as metricas do modelo, e manda junto com a pergunta. O LLM so le e explica.

Consequencias de seguranca: o LLM nunca toca em banco nenhum e nao tem
ferramenta nenhuma - nem de leitura. Tudo o que ele sabe esta neste texto.

Ordem do prompt: primeiro a parte FIXA (instrucoes e arquitetura), depois
os DADOS. O Ollama reaproveita o processamento do comeco do prompt quando
ele se repete entre perguntas; com a parte fixa na frente, so os dados e a
pergunta precisam ser processados de novo - na CPU isso corta segundos.
"""

from datetime import UTC, datetime

from sqlalchemy import select

from app.alertas.models import Alerta
from app.core.database import SessionLocal
from app.dispositivos.models import Dispositivo
from app.ia.models import Modelo
from app.tempo_real.hub import hub

INSTRUCOES = """Você é o assistente do Gas-Guard, um sistema AIoT que monitora vazamento de gás GLP em uma cozinha comercial e faz manutenção preditiva do exaustor da coifa.

Regras:
- Responda sempre em português do Brasil, de forma curta e direta: no máximo 100 palavras (dois parágrafos curtos ou uma lista de até 4 itens).
- Use SOMENTE os dados da seção DADOS ATUAIS abaixo. Se a informação não estiver lá, diga que não tem esse dado. Nunca invente números.
- Quando falar de um número, diga a unidade e de onde ele vem (sensor, previsão da IA, métrica do modelo).
- Pode usar Markdown simples (negrito, listas). Não use HTML nem imagens.

Como o sistema funciona:
- Um simulador em Python faz o papel dos dispositivos e publica as leituras por MQTT no Mosquitto.
- O gateway lê o MQTT e republica cada mensagem no RabbitMQ (exchange gg.telemetria, routing key telemetry.<zona>.<tipo>.<dispositivo>).
- Do RabbitMQ, cada serviço consome a sua fila: o gravador grava no InfluxDB (séries temporais), o serviço de regras aciona atuadores e abre alertas, a inferência aplica os modelos de IA, e a API entrega tudo ao navegador por WebSocket.
- Comandos fazem o caminho inverso: botão no painel -> API -> RabbitMQ -> gateway -> MQTT -> simulador.
- PostgreSQL guarda cadastro, usuários, regras, alertas e auditoria. InfluxDB guarda leituras e previsões.
- Mosquitto é o protocolo de borda (leve, para dispositivos); RabbitMQ é o barramento interno (filas duráveis, vários consumidores, fila de mensagens mortas).

Sobre a IA:
- Dois modelos de regressão (HistGradientBoosting, scikit-learn) treinados com dados sintéticos do Laboratório: índice de saúde (0 a 100) e vida útil restante em horas de operação (até 96 h; acima disso a máquina é considerada sem falha à vista).
- As entradas são médias, desvios, máximos e tendências das últimas leituras de vibração, corrente, temperatura e rotação, e o quanto cada uma se afastou de como a máquina era quando nova.
- O treino separa máquinas inteiras entre treino, validação e teste, e o modelo só entra em uso se vencer uma base simples que sempre prevê a média.
- MAE é o erro médio absoluto (quanto o modelo erra, em média, na unidade do alvo). R² vai até 1: quanto mais perto de 1, mais o modelo explica a variação.
- No ao vivo, cada leitura do exaustor vale 5 minutos de operação (tempo acelerado para a demonstração).
- Alertas usam histerese: abrem depois de 3 previsões seguidas abaixo do limite e só fecham depois de 10 seguidas acima do limite com folga, para não ficarem piscando.

O que costuma significar cada sinal no exaustor e o que fazer:
- Vibração subindo muito, com temperatura subindo: desgaste de rolamento. Programar troca do rolamento.
- Vibração subindo de forma constante: desbalanceamento, geralmente gordura acumulada nas pás. Limpar o rotor.
- Corrente caindo com rotação subindo e motor esquentando: filtro de gordura entupido (o ventilador move menos ar). Limpar ou trocar os filtros da coifa.
- Temperatura do motor disparando com corrente alta: superaquecimento. Verificar ventilação e isolamento do motor.
- Se o exaustor parar, o gás acumula na cozinha: por isso a falha dele é crítica para a segurança.

Faixas do gás GLP: normal abaixo de 1000 ppm, atenção de 1000 a 2000 ppm, crítico acima de 2000 ppm (cerca de 10% do limite inferior de explosividade, 19000 ppm). Com 2000 ppm a válvula solenoide fecha sozinha e a sirene liga; o operador reabre a válvula pelo painel."""


SEVERIDADE = {"atencao": "atenção", "critico": "crítico"}
ORIGEM = {
    "limite": "leitura fora da faixa",
    "ia_saude": "previsão de saúde da IA",
    "ia_rul": "previsão de vida útil da IA",
    "falha": "equipamento parou",
}


def _ha_quanto(instante: datetime | str | None) -> str:
    if instante is None:
        return "?"
    if isinstance(instante, str):
        instante = datetime.fromisoformat(instante)
    segundos = int((datetime.now(UTC) - instante).total_seconds())
    if segundos < 60:
        return f"{segundos} s"
    if segundos < 3600:
        return f"{segundos // 60} min"
    return f"{segundos // 3600} h"


def _formatar(valor) -> str:
    if isinstance(valor, float):
        return f"{valor:.1f}".replace(".", ",")
    return str(valor)


def montar() -> str:
    """Instrucoes fixas + DADOS ATUAIS. Roda numa thread (consulta o banco)."""
    with SessionLocal() as db:
        dispositivos = {d.codigo: d for d in db.scalars(select(Dispositivo)).all()}
        alertas = db.scalars(
            select(Alerta).where(Alerta.ativo.is_(True)).order_by(Alerta.atualizado_em.desc())
        ).all()
        modelo = db.scalars(select(Modelo).where(Modelo.ativo.is_(True))).first()

        linhas = [INSTRUCOES, "", "DADOS ATUAIS", f"Agora: {datetime.now(UTC):%d/%m/%Y %H:%M} UTC"]

        sem_dados = hub.segundos_sem_telemetria()
        if sem_dados is None:
            linhas.append("Simulador: nenhuma leitura recebida desde que a API subiu.")
        elif sem_dados > 10:
            linhas.append(f"Simulador: SEM DADOS há {int(sem_dados)} s (parado ou fora do ar).")
        else:
            linhas.append("Simulador: enviando dados normalmente.")

        linhas.append("\nLeituras mais recentes:")
        for codigo, mensagem in sorted(hub.telemetria.items()):
            d = dispositivos.get(codigo)
            nome = d.nome if d else codigo
            conteudo = mensagem.get("conteudo", {})
            partes = [f"{campo} {_formatar(valor)}" for campo, valor in (conteudo.get("leituras") or {}).items()]
            if conteudo.get("estado"):
                partes.append(f"estado {conteudo['estado']}")
            situacao = ""
            if d and d.campo_principal and d.campo_principal in (conteudo.get("leituras") or {}):
                situacao = f" -> {d.classificar(conteudo['leituras'][d.campo_principal])}"
            linhas.append(
                f"- {codigo} ({nome}): {', '.join(partes) or 'sem leitura'}{situacao}"
                f" (há {_ha_quanto(mensagem.get('instante'))})"
            )

        linhas.append("\nPrevisões da IA:")
        if not hub.insights:
            linhas.append("- nenhuma previsão recebida ainda")
        for codigo, mensagem in hub.insights.items():
            c = mensagem.get("conteudo", {})
            if c.get("estado_ia") == "ok":
                linhas.append(
                    f"- {codigo}: saúde {_formatar(c.get('saude'))}/100, vida útil restante "
                    f"~{_formatar(c.get('rul_horas'))} h de operação, tendência {c.get('tendencia')} "
                    f"({_formatar(c.get('inclinacao_saude'))} pontos/h), modelo {c.get('versao_modelo')}"
                )
            else:
                linhas.append(f"- {codigo}: {c.get('estado_ia')} (estado do motor: {c.get('estado_operacao')})")

        linhas.append("\nAlertas abertos:")
        if not alertas:
            linhas.append("- nenhum")
        for alerta in alertas[:10]:
            linhas.append(
                f"- [{SEVERIDADE.get(alerta.severidade, alerta.severidade)}] {alerta.dispositivo_codigo} "
                f"({ORIGEM.get(alerta.chave, alerta.chave)}): "
                f"{alerta.mensagem} - aberto há {_ha_quanto(alerta.aberto_em)}"
            )

        if hub.acionamentos:
            linhas.append("\nÚltimos acionamentos automáticos por regra:")
            for item in list(hub.acionamentos)[:5]:
                c = item.get("conteudo", {})
                linhas.append(
                    f"- regra '{c.get('regra')}': {c.get('acao')} {c.get('alvo')} porque "
                    f"{c.get('gatilho')} {c.get('campo')} = {_formatar(c.get('valor'))} "
                    f"({c.get('condicao')}), há {_ha_quanto(item.get('instante'))}"
                )

        linhas.append("\nModelo em uso:")
        if modelo is None:
            linhas.append("- nenhum modelo treinado/ativo ainda (gere dados no Laboratório e treine).")
        else:
            m = modelo.metricas or {}
            dados = m.get("dados", {})
            linhas.append(
                f"- versão {modelo.versao}, treinado em {modelo.criado_em:%d/%m %H:%M}, "
                f"dataset {dados.get('dataset')}, {dados.get('linhas_usadas')} linhas, "
                f"máquinas treino/validação/teste = {dados.get('maquinas')}"
            )
            for info in (m.get("alvos") or {}).values():
                teste = info["avaliacao"]["teste"]
                linhas.append(
                    f"- {info['nome']}: MAE {_formatar(teste['modelo']['mae'])} {info['unidade']} "
                    f"(base simples {_formatar(teste['base']['mae'])}), R² {_formatar(teste['modelo']['r2'])}, "
                    f"{'venceu' if info['venceu_base'] else 'NÃO venceu'} a base; "
                    f"atributos mais importantes: {', '.join(n for n, _ in info['importancia'][:3])}"
                )

    return "\n".join(linhas)
