<script setup lang="ts">
// Painel: tudo ao vivo pelo WebSocket. O historico (periodos maiores que
// 5 min) vem do InfluxDB pela API.
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { comandarSimulador, historico, mensagemDeErro, type Ponto } from '../api/client'
import type { Dispositivo, Estado } from '../api/types'
import BotoesComando from '../components/BotoesComando.vue'
import GraficoSerie, { type SerieGrafico } from '../components/GraficoSerie.vue'
import MiniGrafico from '../components/MiniGrafico.vue'
import SeloEstado from '../components/SeloEstado.vue'
import { COR_ESTADO, estadoDoDispositivo } from '../lib/estado'
import { dataHora, fmt, hora, haQuanto, ROTULO_CAMPO, UNIDADE_CAMPO } from '../lib/formato'
import { useAuth } from '../stores/auth'
import { useCadastro } from '../stores/cadastro'
import { useTempoReal } from '../stores/tempoReal'

const auth = useAuth()
const cadastro = useCadastro()
const tempoReal = useTempoReal()

const CORES = ['#0b6e75', '#b4532a', '#6a4fb3', '#2e7d5b']

const sensores = computed(() => cadastro.ativos.filter((d) => d.categoria === 'sensor'))
const atuadores = computed(() => cadastro.ativos.filter((d) => d.categoria !== 'sensor'))

function estado(d: Dispositivo): Estado {
  void tempoReal.versao
  return estadoDoDispositivo(
    d,
    tempoReal.bruto.telemetria[d.codigo],
    tempoReal.bruto.insights[d.codigo],
    cadastro.alertas,
    tempoReal.semDados(d.codigo),
  )
}

function leitura(d: Dispositivo) {
  void tempoReal.versao
  return tempoReal.bruto.telemetria[d.codigo]
}

function valorPrincipal(d: Dispositivo): number | undefined {
  return d.campo_principal ? leitura(d)?.leituras[d.campo_principal] : undefined
}

function serieViva(d: Dispositivo, campo: string | null): number[] {
  void tempoReal.versao
  if (!campo) return []
  return [...(tempoReal.bruto.series[d.codigo]?.[campo]?.v ?? [])]
}

function insight(codigo: string) {
  void tempoReal.versao
  return tempoReal.bruto.insights[codigo]
}

const ROTULO_IA: Record<string, string> = {
  aquecendo: 'juntando leituras',
  sem_modelo: 'sem modelo treinado',
  parado: 'motor parado',
  falha: 'em falha',
}

// ---------- grafico principal ----------
const selecionado = ref('GAS-01')
const minutos = ref(0) // 0 = ao vivo (buffer do WebSocket)
const pontosHistorico = ref<Ponto[]>([])
const erroHistorico = ref<string | null>(null)
let temporizador: ReturnType<typeof setInterval> | undefined

const dispositivoSelecionado = computed(() => cadastro.porCodigo[selecionado.value])

async function carregarHistorico(): Promise<void> {
  if (minutos.value === 0) return
  try {
    pontosHistorico.value = await historico(selecionado.value, minutos.value)
    erroHistorico.value = null
  } catch (causa) {
    erroHistorico.value = mensagemDeErro(causa)
  }
}

watch([selecionado, minutos], () => {
  pontosHistorico.value = []
  carregarHistorico()
})

onMounted(() => {
  temporizador = setInterval(carregarHistorico, 10000)
})
onUnmounted(() => clearInterval(temporizador))

const camposDoGrafico = computed(() => {
  const d = dispositivoSelecionado.value
  if (!d) return []
  if (d.tipo === 'exaustor') return ['vibracao', 'corrente', 'temperatura']
  if (d.categoria === 'atuador') return ['acionado']
  return d.campo_principal ? [d.campo_principal] : []
})

const seriesGrafico = computed<SerieGrafico[]>(() => {
  void tempoReal.versao
  return camposDoGrafico.value.map((campo, i) => {
    let pontos: { x: number; y: number }[]
    if (minutos.value === 0) {
      const s = tempoReal.bruto.series[selecionado.value]?.[campo]
      pontos = s ? s.t.map((t, j) => ({ x: t, y: s.v[j] })) : []
    } else {
      pontos = pontosHistorico.value
        .filter((p) => typeof p[campo] === 'number')
        .map((p) => ({ x: Date.parse(p.horario), y: p[campo] as number }))
    }
    return { rotulo: ROTULO_CAMPO[campo] ?? campo, cor: CORES[i % CORES.length], pontos }
  })
})

const limitesGrafico = computed(() => {
  const d = dispositivoSelecionado.value
  if (!d || camposDoGrafico.value.length !== 1) return []
  const lista: { valor: number; rotulo: string; cor: string }[] = []
  if (d.normal_max !== null) lista.push({ valor: d.normal_max, rotulo: 'Atenção', cor: COR_ESTADO.atencao })
  if (d.critico_max !== null) lista.push({ valor: d.critico_max, rotulo: 'Crítico', cor: COR_ESTADO.critico })
  return lista
})

// ---------- controles do simulador ----------
const retornoSimulador = ref<string | null>(null)
async function simulador(comando: Record<string, unknown>, texto: string): Promise<void> {
  try {
    await comandarSimulador(comando)
    retornoSimulador.value = `${texto}: comando enviado (API → RabbitMQ → gateway → MQTT → simulador).`
  } catch (causa) {
    retornoSimulador.value = mensagemDeErro(causa)
  }
}
</script>

<template>
  <div class="pagina">
    <p v-if="!cadastro.carregado" class="gg-vazio">Carregando cadastro…</p>

    <!-- sensores -->
    <section class="grade-sensores">
      <button
        v-for="d in sensores"
        :key="d.codigo"
        type="button"
        class="sensor gg-cartao"
        :data-estado="estado(d)"
        :class="{ ativo: selecionado === d.codigo }"
        @click="selecionado = d.codigo"
      >
        <div class="sensor-topo">
          <span class="nome">{{ d.nome }}</span>
          <SeloEstado :estado="estado(d)" />
        </div>
        <p class="valor">
          {{ fmt(valorPrincipal(d), d.campo_principal === 'ppm' || d.campo_principal === 'lux' ? 0 : 1) }}
          <small>{{ d.unidade }}</small>
        </p>
        <MiniGrafico :valores="serieViva(d, d.campo_principal)" :cor="COR_ESTADO[estado(d)]" />
        <span class="rodape">{{ d.codigo }} · {{ haQuanto(leitura(d)?.instante) }}</span>
      </button>
    </section>

    <!-- atuadores e equipamento -->
    <section class="grade-atuadores">
      <article v-for="d in atuadores" :key="d.codigo" class="gg-cartao atuador" :data-estado="estado(d)">
        <div class="sensor-topo">
          <button type="button" class="nome link" @click="selecionado = d.codigo">{{ d.nome }}</button>
          <SeloEstado :estado="estado(d)" />
        </div>
        <p class="estado-atuador">{{ leitura(d)?.estado ?? '—' }}</p>

        <dl v-if="d.tipo === 'exaustor'" class="medidas">
          <div v-for="campo in ['vibracao', 'corrente', 'temperatura', 'rpm']" :key="campo">
            <dt>{{ ROTULO_CAMPO[campo] }}</dt>
            <dd>{{ fmt(leitura(d)?.leituras[campo], campo === 'rpm' ? 0 : 1) }} {{ UNIDADE_CAMPO[campo] }}</dd>
          </div>
          <div>
            <dt>Saúde (IA)</dt>
            <dd>{{ insight(d.codigo)?.estado_ia === 'ok' ? `${fmt(insight(d.codigo)?.saude, 0)}/100` : ROTULO_IA[insight(d.codigo)?.estado_ia ?? ''] ?? '—' }}</dd>
          </div>
          <div>
            <dt>Vida útil (IA)</dt>
            <dd>{{ insight(d.codigo)?.estado_ia === 'ok' ? `${fmt(insight(d.codigo)?.rul_horas, 0)} h` : '—' }}</dd>
          </div>
        </dl>

        <BotoesComando :codigo="d.codigo" :tipo="d.tipo" :estado="leitura(d)?.estado ?? null" />
      </article>
    </section>

    <!-- grafico principal -->
    <section class="gg-cartao">
      <div class="cabecalho-grafico">
        <h2 class="gg-titulo">{{ dispositivoSelecionado?.nome ?? selecionado }}</h2>
        <div class="controles">
          <select v-model="selecionado" class="gg-select">
            <option v-for="d in cadastro.ativos" :key="d.codigo" :value="d.codigo">{{ d.nome }} ({{ d.codigo }})</option>
          </select>
          <select v-model.number="minutos" class="gg-select">
            <option :value="0">Ao vivo (5 min, WebSocket)</option>
            <option :value="30">30 min (InfluxDB)</option>
            <option :value="60">1 hora</option>
            <option :value="360">6 horas</option>
            <option :value="1440">24 horas</option>
          </select>
        </div>
      </div>
      <p v-if="erroHistorico" class="gg-alerta gg-alerta--erro">{{ erroHistorico }}</p>
      <GraficoSerie
        :series="seriesGrafico"
        :limites="limitesGrafico"
        :unidade="camposDoGrafico.length === 1 ? (UNIDADE_CAMPO[camposDoGrafico[0]] ?? '') : ''"
        :min-y="camposDoGrafico[0] === 'acionado' ? 0 : undefined"
        :max-y="camposDoGrafico[0] === 'acionado' ? 1.05 : undefined"
      />
    </section>

    <!-- simulador (operador) -->
    <section v-if="auth.pode('operador')" class="gg-cartao">
      <h2 class="gg-titulo">Simulador da cozinha</h2>
      <div class="linha-botoes">
        <button type="button" class="gg-btn" @click="simulador({ acao: 'vazamento', intensidade: 0.3 }, 'Vazamento leve')">Vazamento leve</button>
        <button type="button" class="gg-btn gg-btn--perigo" @click="simulador({ acao: 'vazamento', intensidade: 1 }, 'Vazamento forte')">Vazamento forte</button>
        <button type="button" class="gg-btn" @click="simulador({ acao: 'vazamento', intensidade: 0 }, 'Vazamento estancado')">Parar vazamento</button>
        <span class="separador" />
        <button type="button" class="gg-btn" @click="simulador({ acao: 'pausar' }, 'Simulador pausado')">Pausar simulador</button>
        <button type="button" class="gg-btn" @click="simulador({ acao: 'retomar' }, 'Simulador retomado')">Retomar</button>
        <span class="separador" />
        <button type="button" class="gg-btn" @click="simulador({ acao: 'relogio', fator: 1 }, 'Relógio em tempo real')">Relógio 1×</button>
        <button type="button" class="gg-btn" @click="simulador({ acao: 'relogio', fator: 120 }, 'Um dia em 12 min')">Relógio 120×</button>
      </div>
      <p v-if="retornoSimulador" class="nota">{{ retornoSimulador }}</p>
      <p class="nota">
        Vazamento leve com o exaustor ligado fica abaixo do crítico; com ele desligado, sobe até a válvula fechar
        sozinha. Para injetar falha no exaustor, use a página Insights ou clique nele no Gêmeo 3D.
      </p>
    </section>

    <!-- alertas e eventos -->
    <section class="duas-colunas">
      <div class="gg-cartao">
        <h2 class="gg-titulo">Alertas abertos ({{ cadastro.alertas.length }})</h2>
        <p v-if="cadastro.alertas.length === 0" class="gg-vazio">Nenhum alerta aberto.</p>
        <ul v-else class="lista">
          <li v-for="a in cadastro.alertas" :key="a.id" :data-severidade="a.severidade">
            <strong>{{ a.dispositivo_codigo }}</strong> {{ a.mensagem }}
            <small>{{ a.origem === 'ia' ? 'IA' : 'limite' }} · aberto {{ haQuanto(a.aberto_em) }}</small>
          </li>
        </ul>
      </div>
      <div class="gg-cartao">
        <h2 class="gg-titulo">Eventos ao vivo</h2>
        <p v-if="tempoReal.eventos.length === 0" class="gg-vazio">Comandos, regras e alertas aparecem aqui.</p>
        <ul v-else class="lista">
          <li v-for="e in tempoReal.eventos.slice(0, 12)" :key="e.id" :data-severidade="e.severidade">
            <span class="hora" :title="dataHora(e.instante)">{{ hora(e.instante) }}</span>
            <span class="etiqueta">{{ e.tipo }}</span> {{ e.texto }}
          </li>
        </ul>
      </div>
    </section>
  </div>
</template>

<style scoped>
.pagina {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}
.grade-sensores {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 1rem;
}
.grade-atuadores {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1rem;
}
.sensor {
  text-align: left;
  font: inherit;
  cursor: pointer;
  border-left: 4px solid var(--gg-ink-2);
  padding: 0.9rem 1rem 0.7rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.sensor.ativo {
  outline: 2px solid var(--gg-ink);
  outline-offset: 1px;
}
.sensor[data-estado='normal'],
.atuador[data-estado='normal'] { border-left-color: var(--gg-ok); }
.sensor[data-estado='atencao'],
.atuador[data-estado='atencao'] { border-left-color: var(--gg-warn); }
.sensor[data-estado='critico'],
.atuador[data-estado='critico'] { border-left-color: var(--gg-crit); }
.atuador {
  border-left: 4px solid var(--gg-ink-2);
  padding: 0.9rem 1rem;
}
.sensor-topo {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  align-items: flex-start;
}
.nome {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--gg-ink);
}
.nome.link {
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
}
.valor {
  margin: 0;
  font-size: 1.9rem;
  font-weight: 650;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}
.valor small {
  font-size: 0.85rem;
  color: var(--gg-ink-2);
  font-weight: 500;
}
.rodape {
  font-size: 0.72rem;
  color: var(--gg-ink-2);
}
.estado-atuador {
  margin: 0.4rem 0 0.6rem;
  font-size: 1.3rem;
  font-weight: 600;
  text-transform: capitalize;
}
.medidas {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.4rem 0.8rem;
  margin: 0 0 0.8rem;
}
.medidas dt {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--gg-ink-2);
}
.medidas dd {
  margin: 0;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.cabecalho-grafico {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.6rem;
  align-items: center;
  margin-bottom: 0.6rem;
}
.cabecalho-grafico .gg-titulo {
  margin: 0;
}
.controles {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.controles .gg-select {
  width: auto;
}
.linha-botoes {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}
.separador {
  width: 1px;
  height: 1.6rem;
  background: var(--gg-line);
  margin: 0 0.2rem;
}
.nota {
  margin: 0.7rem 0 0;
  font-size: 0.84rem;
  color: var(--gg-ink-2);
}
.duas-colunas {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1rem;
}
.lista {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  font-size: 0.88rem;
}
.lista li {
  padding: 0.45rem 0.6rem;
  border-radius: 5px;
  background: var(--gg-surface-2);
  border-left: 3px solid var(--gg-line);
}
.lista li[data-severidade='atencao'] { border-left-color: var(--gg-warn); }
.lista li[data-severidade='critico'] { border-left-color: var(--gg-crit); }
.lista small {
  display: block;
  color: var(--gg-ink-2);
  font-size: 0.75rem;
}
.hora {
  font-family: var(--gg-mono);
  font-size: 0.78rem;
  color: var(--gg-ink-2);
  margin-right: 0.3rem;
}
.etiqueta {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.05rem 0.35rem;
  border-radius: 3px;
  background: var(--gg-surface);
  border: 1px solid var(--gg-line);
  margin-right: 0.3rem;
}
</style>
