<script setup lang="ts">
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from 'chart.js'
import { computed, onMounted, ref, watch } from 'vue'
import { Bar, Scatter } from 'vue-chartjs'

import {
  ativarModelo,
  detalharModelo,
  listarJobs,
  listarModelos,
  mensagemDeErro,
  treinar,
} from '../api/client'
import type { Job, ModeloDetalhe, ModeloResumo, ResultadoAlvo } from '../api/types'
import { dataHora, fmt, fmtMil } from '../lib/formato'
import { useAuth } from '../stores/auth'
import { useTempoReal } from '../stores/tempoReal'

ChartJS.register(LinearScale, CategoryScale, PointElement, LineElement, BarElement, Tooltip)

const auth = useAuth()
const tempoReal = useTempoReal()

const datasets = ref<Job[]>([])
const treinos = ref<Job[]>([])
const modelos = ref<ModeloResumo[]>([])
const detalhe = ref<ModeloDetalhe | null>(null)
const versaoAberta = ref<string | null>(null)
const datasetEscolhido = ref<number | null>(null)
const maxLinhas = ref(400000)
const erro = ref<string | null>(null)
const enviando = ref(false)

async function carregar(): Promise<void> {
  const [gerados, treinados, lista] = await Promise.all([listarJobs('gerar'), listarJobs('treinar'), listarModelos()])
  datasets.value = gerados.filter((j) => j.status === 'concluido')
  treinos.value = treinados
  modelos.value = lista
  if (datasetEscolhido.value === null) datasetEscolhido.value = datasets.value[0]?.id ?? null
  const alvo = versaoAberta.value ?? lista.find((m) => m.ativo)?.versao ?? lista[0]?.versao
  if (alvo) await abrir(alvo)
}

async function abrir(versao: string): Promise<void> {
  versaoAberta.value = versao
  detalhe.value = await detalharModelo(versao)
}

onMounted(carregar)
watch(() => [tempoReal.jobsMudaram, tempoReal.modelosMudaram], () => {
  versaoAberta.value = null
  carregar()
})

async function iniciarTreino(): Promise<void> {
  if (datasetEscolhido.value === null) return
  enviando.value = true
  erro.value = null
  try {
    await treinar(datasetEscolhido.value, maxLinhas.value)
    treinos.value = await listarJobs('treinar')
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  } finally {
    enviando.value = false
  }
}

async function ativar(versao: string): Promise<void> {
  try {
    await ativarModelo(versao)
    modelos.value = await listarModelos()
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  }
}

function progresso(job: Job): { fracao: number; etapa: string; status: string } {
  const vivo = tempoReal.progressoJobs[job.id]
  if (vivo && job.status !== 'concluido' && job.status !== 'falhou') {
    return { fracao: Number(vivo.progresso ?? 0), etapa: String(vivo.etapa ?? ''), status: String(vivo.status) }
  }
  return { fracao: job.status === 'concluido' ? 1 : job.progresso, etapa: job.etapa ?? '', status: job.status }
}

const alvos = computed(() => Object.entries(detalhe.value?.metricas.alvos ?? {}) as [string, ResultadoAlvo][])

const NOME_CONJUNTO: Record<string, string> = {
  validacao: 'Validação',
  teste: 'Teste',
  teste_degradando: 'Teste, só máquinas degradando',
}

function dispersao(alvo: ResultadoAlvo): ChartData<'scatter'> {
  const [min, max] = alvo.limites
  return {
    datasets: [
      {
        label: 'linhas do teste',
        data: alvo.dispersao.map(([x, y]) => ({ x, y })),
        backgroundColor: 'rgba(11, 110, 117, 0.35)',
        pointRadius: 2.5,
      },
      {
        label: 'acerto perfeito',
        data: [{ x: min, y: min }, { x: max, y: max }],
        showLine: true,
        borderColor: 'rgba(169, 59, 44, 0.7)',
        borderDash: [6, 4],
        pointRadius: 0,
      },
    ],
  }
}

function opcoesDispersao(alvo: ResultadoAlvo): ChartOptions<'scatter'> {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { min: alvo.limites[0], max: alvo.limites[1], title: { display: true, text: `real (${alvo.unidade})` } },
      y: { min: alvo.limites[0], max: alvo.limites[1], title: { display: true, text: `previsto (${alvo.unidade})` } },
    },
  }
}

function importancia(alvo: ResultadoAlvo): ChartData<'bar'> {
  const itens = alvo.importancia.slice(0, 10)
  return {
    labels: itens.map(([nome]) => nome),
    datasets: [{ data: itens.map(([, v]) => v), backgroundColor: '#0b6e75' }],
  }
}

const opcoesImportancia: ChartOptions<'bar'> = {
  indexAxis: 'y',
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  plugins: { legend: { display: false }, tooltip: { callbacks: { label: (i) => `aumento do erro: ${Number(i.parsed.x).toFixed(3)}` } } },
  scales: { x: { title: { display: true, text: 'quanto o erro (MAE) piora sem o atributo' } }, y: { ticks: { font: { size: 11 } } } },
}
</script>

<template>
  <div class="pagina">
    <section class="gg-cartao">
      <h2 class="gg-titulo">Treinar os modelos de regressão</h2>
      <p class="intro">
        Dois modelos (HistGradientBoosting, scikit-learn) aprendem com o dataset escolhido: o <strong>índice de
        saúde</strong> (0 a 100) e a <strong>vida útil restante</strong> (horas até a falha). As máquinas são divididas
        inteiras entre treino (70%), validação (15%) e teste (15%), e o modelo só entra em uso sozinho se vencer a
        <strong>base simples</strong>, que sempre responde a média do treino. O treino roda no serviço
        <code>lab</code>, pela fila <code>q.jobs.treinar</code>; a inferência troca para a versão nova sem reiniciar.
      </p>
      <p v-if="erro" class="gg-alerta gg-alerta--erro">{{ erro }}</p>
      <div class="gg-form">
        <label class="gg-campo">
          <span>Dataset</span>
          <select v-model.number="datasetEscolhido" class="gg-select">
            <option v-for="d in datasets" :key="d.id" :value="d.id">
              ds{{ d.id }} · {{ fmtMil(d.resultado?.leituras as number) }} leituras · {{ dataHora(d.concluido_em) }}
            </option>
          </select>
        </label>
        <label class="gg-campo">
          <span>Máximo de linhas no treino</span>
          <input v-model.number="maxLinhas" class="gg-input" type="number" min="10000" max="3000000" step="10000" />
        </label>
      </div>
      <p v-if="datasets.length === 0" class="nota">Nenhum dataset pronto: gere um no Laboratório de dados.</p>
      <div class="gg-acoes">
        <button v-if="auth.pode('administrador')" type="button" class="gg-btn gg-btn--primario"
                :disabled="enviando || datasetEscolhido === null" @click="iniciarTreino">
          {{ enviando ? 'Enfileirando…' : 'Treinar' }}
        </button>
        <p v-else class="nota">Treinar é permitido ao administrador.</p>
      </div>

      <div v-for="job in treinos.slice(0, 4)" :key="job.id" class="job" :data-status="progresso(job).status">
        <span>treino #{{ job.id }} (ds{{ job.parametros.dataset_job_id }})</span>
        <div class="barra"><div :style="{ width: `${Math.round(progresso(job).fracao * 100)}%` }" /></div>
        <small>{{ progresso(job).status }} · {{ Math.round(progresso(job).fracao * 100) }}% · {{ progresso(job).etapa }}
          <template v-if="job.resultado">· {{ job.resultado.versao }} {{ job.resultado.ativado ? 'em uso' : 'não ativado (não venceu a base)' }}</template>
        </small>
        <p v-if="job.erro" class="gg-alerta gg-alerta--erro">{{ job.erro }}</p>
      </div>
    </section>

    <section class="gg-cartao">
      <h2 class="gg-titulo">Versões</h2>
      <p v-if="modelos.length === 0" class="gg-vazio">Nenhum modelo treinado ainda.</p>
      <div v-else class="gg-rolagem">
        <table class="gg-tabela">
          <thead><tr><th>Versão</th><th>Dataset</th><th>Treinado em</th><th>Venceu a base</th><th>Situação</th><th></th></tr></thead>
          <tbody>
            <tr v-for="m in modelos" :key="m.id" :class="{ aberta: m.versao === versaoAberta }">
              <td><button type="button" class="link" @click="abrir(m.versao)">{{ m.versao }}</button></td>
              <td>ds{{ m.dataset_job_id }}</td>
              <td class="gg-num">{{ dataHora(m.criado_em) }}</td>
              <td>{{ m.venceu_base ? 'sim' : 'não' }}</td>
              <td><span class="gg-selo" :class="m.ativo ? 'gg-selo--ok' : 'gg-selo--off'">{{ m.ativo ? 'em uso' : 'guardado' }}</span></td>
              <td>
                <button v-if="!m.ativo && auth.pode('administrador')" type="button" class="gg-btn gg-btn--mini" @click="ativar(m.versao)">
                  Usar esta versão
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <template v-if="detalhe">
      <section class="gg-cartao">
        <h2 class="gg-titulo">Modelo {{ detalhe.versao }} · como foi treinado</h2>
        <dl class="dados">
          <div><dt>Dataset</dt><dd>{{ detalhe.metricas.dados.dataset }}</dd></div>
          <div><dt>Linhas usadas</dt><dd>{{ fmtMil(detalhe.metricas.dados.linhas_usadas) }}</dd></div>
          <div><dt>Máquinas treino / validação / teste</dt>
            <dd>{{ detalhe.metricas.dados.maquinas.treino }} / {{ detalhe.metricas.dados.maquinas.validacao }} / {{ detalhe.metricas.dados.maquinas.teste }}</dd></div>
          <div><dt>Atributos (features)</dt><dd>{{ detalhe.metricas.dados.features }}</dd></div>
          <div><dt>Janelas (amostras de 5 min)</dt>
            <dd>{{ Object.entries(detalhe.metricas.dados.janelas).map(([k, v]) => `${k} ${v}`).join(' · ') }}</dd></div>
          <div><dt>Tempo de treino</dt><dd>{{ detalhe.metricas.segundos }} s</dd></div>
        </dl>
        <p class="nota">
          <strong>MAE</strong>: erro médio, na unidade do alvo (quanto o modelo erra, em média).
          <strong>RMSE</strong>: parecido, mas pune mais os erros grandes.
          <strong>R²</strong>: quanto da variação o modelo explica (1 = tudo; 0 = igual a chutar a média).
          A linha "só máquinas degradando" mostra o caso difícil, que é o que importa para a manutenção.
        </p>
      </section>

      <section v-for="[chave, alvo] in alvos" :key="chave" class="gg-cartao alvo">
        <div class="alvo-topo">
          <h2 class="gg-titulo">{{ alvo.nome }} ({{ alvo.unidade }})</h2>
          <span class="gg-selo" :class="alvo.venceu_base ? 'gg-selo--ok' : 'gg-selo--off'">
            {{ alvo.venceu_base ? `venceu a base: erro ${alvo.ganho_sobre_base_pct}% menor` : 'não venceu a base' }}
          </span>
        </div>
        <div class="gg-rolagem">
          <table class="gg-tabela">
            <thead>
              <tr><th>Conjunto</th><th>Linhas</th><th>MAE modelo</th><th>MAE base</th><th>RMSE modelo</th><th>RMSE base</th><th>R² modelo</th><th>R² base</th></tr>
            </thead>
            <tbody>
              <tr v-for="(av, conjunto) in alvo.avaliacao" :key="conjunto">
                <td>{{ NOME_CONJUNTO[conjunto] ?? conjunto }}</td>
                <td class="gg-num">{{ fmtMil(av.linhas) }}</td>
                <td class="gg-num"><strong>{{ fmt(av.modelo.mae, 2) }}</strong></td>
                <td class="gg-num">{{ fmt(av.base.mae, 2) }}</td>
                <td class="gg-num">{{ fmt(av.modelo.rmse, 2) }}</td>
                <td class="gg-num">{{ fmt(av.base.rmse, 2) }}</td>
                <td class="gg-num"><strong>{{ fmt(av.modelo.r2, 2) }}</strong></td>
                <td class="gg-num">{{ fmt(av.base.r2, 2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="graficos">
          <div>
            <p class="rotulo">Previsto × real (amostra do teste)</p>
            <div class="caixa"><Scatter :data="dispersao(alvo)" :options="opcoesDispersao(alvo)" /></div>
          </div>
          <div>
            <p class="rotulo">Importância dos atributos (permutação no teste)</p>
            <div class="caixa"><Bar :data="importancia(alvo)" :options="opcoesImportancia" /></div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.pagina {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}
.intro,
.nota {
  margin: 0 0 1rem;
  color: var(--gg-ink-2);
  font-size: 0.9rem;
}
.nota {
  margin: 0.8rem 0 0;
  font-size: 0.84rem;
}
code {
  font-family: var(--gg-mono);
  font-size: 0.88em;
  background: var(--gg-surface-2);
  padding: 0.05em 0.3em;
  border-radius: 3px;
}
.job {
  margin-top: 0.9rem;
  font-size: 0.88rem;
}
.job small {
  color: var(--gg-ink-2);
}
.barra {
  height: 6px;
  border-radius: 3px;
  background: var(--gg-line-soft);
  margin: 0.35rem 0 0.2rem;
  overflow: hidden;
}
.barra div {
  height: 100%;
  background: var(--gg-ok);
  transition: width 0.4s;
}
.link {
  border: none;
  background: none;
  padding: 0;
  font: inherit;
  font-weight: 600;
  color: #0b6e75;
  cursor: pointer;
  text-decoration: underline;
}
tr.aberta td {
  background: var(--gg-surface-2);
}
.dados {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 0.6rem 1rem;
  margin: 0;
}
.dados dt,
.rotulo {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--gg-ink-2);
  margin: 0 0 0.2rem;
}
.dados dd {
  margin: 0;
  font-weight: 600;
}
.alvo-topo {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 1rem;
  flex-wrap: wrap;
}
.graficos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.2rem;
  margin-top: 1rem;
}
.caixa {
  height: 300px;
  position: relative;
}
</style>
