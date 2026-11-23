<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { comandarSimulador, historicoInsights, listarAlertas, mensagemDeErro, type Ponto } from '../api/client'
import type { Alerta } from '../api/types'
import GraficoSerie, { type SerieGrafico } from '../components/GraficoSerie.vue'
import MedidorSaude from '../components/MedidorSaude.vue'
import SeloEstado from '../components/SeloEstado.vue'
import { COR_ESTADO, estadoDoDispositivo } from '../lib/estado'
import { dataHora, fmt, haQuanto } from '../lib/formato'
import { useAuth } from '../stores/auth'
import { useCadastro } from '../stores/cadastro'
import { useTempoReal } from '../stores/tempoReal'

const auth = useAuth()
const cadastro = useCadastro()
const tempoReal = useTempoReal()

const equipamentos = computed(() => cadastro.ativos.filter((d) => d.categoria === 'equipamento'))
const minutos = ref(30)
const historicos = ref<Record<string, Ponto[]>>({})
const alertasIa = ref<Alerta[]>([])
let temporizador: ReturnType<typeof setInterval> | undefined

async function carregar(): Promise<void> {
  for (const d of equipamentos.value) {
    try {
      historicos.value = { ...historicos.value, [d.codigo]: await historicoInsights(d.codigo, minutos.value) }
    } catch {
      // sem historico ainda: o grafico mostra vazio
    }
  }
  alertasIa.value = (await listarAlertas(false, 100)).filter((a) => a.origem === 'ia' || a.chave === 'falha')
}

watch([minutos, () => equipamentos.value.length], carregar)
watch(() => tempoReal.alertasMudaram, () => setTimeout(carregar, 800))
onMounted(() => {
  carregar()
  temporizador = setInterval(carregar, 15000)
})
onUnmounted(() => clearInterval(temporizador))

function insight(codigo: string) {
  void tempoReal.versao
  return tempoReal.bruto.insights[codigo]
}

function estado(codigo: string) {
  void tempoReal.versao
  const d = cadastro.porCodigo[codigo]
  return estadoDoDispositivo(d, tempoReal.bruto.telemetria[codigo], insight(codigo), cadastro.alertas, tempoReal.semDados(codigo))
}

function series(codigo: string): SerieGrafico[] {
  void tempoReal.versao
  const pontos = (historicos.value[codigo] ?? [])
    .filter((p) => typeof p.saude === 'number')
    .map((p) => ({ x: Date.parse(p.horario), y: p.saude as number }))
  const vivo = tempoReal.bruto.seriesSaude[codigo]
  // o historico vem do Influx; as previsoes mais novas, do WebSocket
  const ultimo = pontos.at(-1)?.x ?? 0
  if (vivo) vivo.t.forEach((t, i) => t > ultimo && pontos.push({ x: t, y: vivo.v[i] }))
  return [{ rotulo: 'Saúde prevista', cor: COR_ESTADO[estado(codigo)], pontos }]
}

const DESCRICAO_ESTADO_IA: Record<string, string> = {
  aquecendo: 'Juntando as primeiras leituras antes de prever',
  sem_modelo: 'Nenhum modelo treinado: gere dados no Laboratório e treine',
  parado: 'Motor desligado: sem vibração e corrente não há o que prever',
  falha: 'O equipamento parou por falha',
}

// ---------- falha injetada (simulador) ----------
const modo = ref('rolamento')
const horas = ref(20)
const retorno = ref<string | null>(null)
async function simular(comando: Record<string, unknown>, texto: string): Promise<void> {
  try {
    await comandarSimulador(comando)
    retorno.value = `${texto}: comando enviado ao simulador.`
  } catch (causa) {
    retorno.value = mensagemDeErro(causa)
  }
}
</script>

<template>
  <div class="pagina">
    <p class="intro">
      Os modelos de regressão rodam no serviço <code>inferencia</code> sobre a telemetria que chega pelo RabbitMQ. As
      previsões voltam pelo barramento (<code>insight.*</code> e <code>alerta.*</code>) e colorem também o exaustor na
      cena 3D. Ao vivo, cada leitura do exaustor vale 5 minutos de operação.
    </p>

    <p v-if="equipamentos.length === 0" class="gg-vazio">Nenhum equipamento cadastrado.</p>

    <article v-for="d in equipamentos" :key="d.codigo" class="gg-cartao equipamento">
      <header class="cabecalho">
        <div>
          <h2>{{ d.nome }}</h2>
          <p class="sub">
            {{ d.codigo }} · motor {{ insight(d.codigo)?.estado_operacao ?? '—' }} ·
            modelo {{ insight(d.codigo)?.versao_modelo ?? 'nenhum' }}
          </p>
        </div>
        <SeloEstado :estado="estado(d.codigo)" />
      </header>

      <div class="corpo">
        <div class="indicadores">
          <MedidorSaude :valor="insight(d.codigo)?.estado_ia === 'ok' || insight(d.codigo)?.estado_ia === 'falha' ? (insight(d.codigo)?.saude ?? null) : null" />
          <dl>
            <div>
              <dt>Vida útil restante</dt>
              <dd>{{ insight(d.codigo)?.rul_horas !== undefined ? `${fmt(insight(d.codigo)?.rul_horas, 0)} h` : '—' }}</dd>
            </div>
            <div>
              <dt>Tendência</dt>
              <dd :data-tendencia="insight(d.codigo)?.tendencia">
                {{ insight(d.codigo)?.tendencia ?? '—' }}
                <small v-if="insight(d.codigo)?.inclinacao_saude !== undefined">({{ fmt(insight(d.codigo)?.inclinacao_saude, 1) }} pts/h)</small>
              </dd>
            </div>
            <div>
              <dt>Leituras na janela</dt>
              <dd>{{ insight(d.codigo)?.amostras ?? '—' }}</dd>
            </div>
          </dl>
          <p v-if="insight(d.codigo) && insight(d.codigo)?.estado_ia !== 'ok'" class="aviso">
            {{ DESCRICAO_ESTADO_IA[insight(d.codigo)?.estado_ia ?? ''] }}
          </p>
          <p v-else-if="!insight(d.codigo)" class="aviso">Aguardando a primeira previsão…</p>
        </div>

        <div class="grafico">
          <div class="cabecalho-grafico">
            <p class="rotulo">Saúde prevista ao longo do tempo</p>
            <select v-model.number="minutos" class="gg-select">
              <option :value="15">15 min</option>
              <option :value="30">30 min</option>
              <option :value="120">2 horas</option>
              <option :value="720">12 horas</option>
            </select>
          </div>
          <GraficoSerie
            :series="series(d.codigo)"
            :min-y="0"
            :max-y="100"
            unidade="pontos"
            :altura="220"
            :limites="[
              { valor: 60, rotulo: 'Atenção', cor: COR_ESTADO.atencao },
              { valor: 30, rotulo: 'Crítico', cor: COR_ESTADO.critico },
            ]"
          />
        </div>
      </div>

      <section class="alertas">
        <h3>Alertas ativos</h3>
        <p v-if="!cadastro.alertas.some((a) => a.dispositivo_codigo === d.codigo)" class="gg-vazio">Nenhum.</p>
        <ul>
          <li v-for="a in cadastro.alertas.filter((x) => x.dispositivo_codigo === d.codigo)" :key="a.id" :data-severidade="a.severidade">
            <strong>{{ a.severidade === 'critico' ? 'Crítico' : 'Atenção' }}</strong> · {{ a.mensagem }}
            <small>{{ a.origem === 'ia' ? 'previsão da IA' : 'limite do sensor' }} · aberto {{ haQuanto(a.aberto_em) }}</small>
          </li>
        </ul>
      </section>

      <section v-if="auth.pode('operador')" class="simulador">
        <h3>Demonstração: injetar falha no simulador</h3>
        <div class="linha">
          <select v-model="modo" class="gg-select">
            <option value="rolamento">Desgaste de rolamento</option>
            <option value="desbalanceamento">Desbalanceamento (gordura nas pás)</option>
            <option value="entupimento">Filtro de gordura entupido</option>
            <option value="superaquecimento">Superaquecimento do motor</option>
            <option value="deriva_sensor">Deriva de sensor (não é desgaste)</option>
            <option value="travamento_sensor">Sensor travado (não é desgaste)</option>
          </select>
          <label class="horas">
            <span>horas de operação até falhar</span>
            <input v-model.number="horas" class="gg-input" type="number" min="16" max="60" />
          </label>
          <button type="button" class="gg-btn gg-btn--perigo"
                  @click="simular({ acao: 'injetar_falha', equipamento: d.codigo, modo, horas_ate_falha: horas, progresso_inicial: 0.35 }, 'Falha injetada')">
            Injetar falha
          </button>
          <button type="button" class="gg-btn" @click="simular({ acao: 'reparar', equipamento: d.codigo }, 'Manutenção feita')">
            Reparar
          </button>
        </div>
        <p class="aviso">
          {{ horas }} h de operação passam em cerca de {{ Math.round((horas * 12 * 2) / 60) }} min de apresentação (cada leitura, a cada 2 s, vale 5 min).
          O simulador nunca publica a saúde verdadeira: quem a descobre é o modelo, pelas leituras.
          <span v-if="retorno"><br />{{ retorno }}</span>
        </p>
      </section>
    </article>

    <section class="gg-cartao">
      <h2 class="gg-titulo">Histórico de alertas preditivos</h2>
      <p v-if="alertasIa.length === 0" class="gg-vazio">Nenhum alerta da IA ainda.</p>
      <div v-else class="gg-rolagem">
        <table class="gg-tabela">
          <thead>
            <tr><th>Situação</th><th>Equipamento</th><th>Tipo</th><th>Mensagem</th><th>Aberto</th><th>Fechado</th></tr>
          </thead>
          <tbody>
            <tr v-for="a in alertasIa" :key="a.id">
              <td><SeloEstado :estado="a.ativo ? (a.severidade === 'critico' ? 'critico' : 'atencao') : 'normal'" :texto="a.ativo ? (a.severidade === 'critico' ? 'crítico' : 'atenção') : 'encerrado'" /></td>
              <td>{{ a.dispositivo_codigo }}</td>
              <td>{{ { ia_saude: 'saúde', ia_rul: 'vida útil', falha: 'falha' }[a.chave] ?? a.chave }}</td>
              <td>{{ a.mensagem }}</td>
              <td class="gg-num">{{ dataHora(a.aberto_em) }}</td>
              <td class="gg-num">{{ dataHora(a.fechado_em) }}</td>
            </tr>
          </tbody>
        </table>
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
.intro {
  margin: 0;
  color: var(--gg-ink-2);
  max-width: 60rem;
}
code {
  font-family: var(--gg-mono);
  font-size: 0.88em;
  background: var(--gg-surface-2);
  padding: 0.05em 0.3em;
  border-radius: 3px;
}
.equipamento {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.cabecalho {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}
.cabecalho h2 {
  margin: 0;
  font-size: 1.1rem;
}
.sub {
  margin: 0.15rem 0 0;
  font-size: 0.82rem;
  color: var(--gg-ink-2);
}
.corpo {
  display: grid;
  grid-template-columns: 15rem minmax(0, 1fr);
  gap: 1.4rem;
}
.indicadores dl {
  margin: 0.4rem 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.indicadores dt,
.rotulo {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--gg-ink-2);
  margin: 0;
}
.indicadores dd {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  text-transform: capitalize;
}
.indicadores dd[data-tendencia='piorando'] { color: var(--gg-crit); }
.indicadores dd small {
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--gg-ink-2);
  text-transform: none;
}
.aviso {
  margin: 0.6rem 0 0;
  font-size: 0.82rem;
  color: var(--gg-ink-2);
}
.cabecalho-grafico {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
}
.cabecalho-grafico .gg-select {
  width: auto;
}
h3 {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
}
.alertas ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.alertas li {
  padding: 0.5rem 0.7rem;
  border-radius: 5px;
  background: var(--gg-surface-2);
  border-left: 3px solid var(--gg-warn);
  font-size: 0.9rem;
}
.alertas li[data-severidade='critico'] { border-left-color: var(--gg-crit); }
.alertas small {
  display: block;
  font-size: 0.75rem;
  color: var(--gg-ink-2);
}
.simulador {
  border-top: 1px solid var(--gg-line-soft);
  padding-top: 0.9rem;
}
.linha {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  align-items: flex-end;
}
.linha .gg-select {
  width: auto;
}
.horas {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  font-size: 0.72rem;
  color: var(--gg-ink-2);
}
.horas .gg-input {
  width: 7rem;
}
@media (max-width: 800px) {
  .corpo {
    grid-template-columns: 1fr;
  }
}
</style>
