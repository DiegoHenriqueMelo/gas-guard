<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { estimarLab, gerarDados, listarJobs, mensagemDeErro, opcoesLab } from '../api/client'
import type { Job } from '../api/types'
import { dataHora, fmtMil } from '../lib/formato'
import { useAuth } from '../stores/auth'
import { useTempoReal } from '../stores/tempoReal'

const auth = useAuth()
const tempoReal = useTempoReal()

const ROTULO_MODO: Record<string, string> = {
  saudavel: 'Saudável',
  rolamento: 'Desgaste de rolamento',
  desbalanceamento: 'Desbalanceamento',
  entupimento: 'Filtro entupido',
  superaquecimento: 'Superaquecimento',
  deriva_sensor: 'Deriva de sensor',
  travamento_sensor: 'Sensor travado',
}

const p = reactive({
  equipamentos: 120,
  sensores_ambiente: { gas: 2, temperatura: 2, umidade: 2, luminosidade: 2 },
  dias: 60,
  pct_falha: 50,
  modos: [] as string[],
  ruido: 0.3,
  pct_faltantes: 1,
  pct_outliers: 0.5,
  semente: 42,
  amostra_influx: true,
})
const modosEquipamento = ref<string[]>([])
const modosSensor = ref<string[]>([])
const maxLeituras = ref(0)
const estimativa = ref<number | null>(null)
const jobs = ref<Job[]>([])
const erro = ref<string | null>(null)
const enviando = ref(false)

async function carregarJobs(): Promise<void> {
  jobs.value = await listarJobs('gerar')
}

onMounted(async () => {
  const opcoes = await opcoesLab()
  Object.assign(p, opcoes.padrao)
  modosEquipamento.value = opcoes.modos_equipamento
  modosSensor.value = opcoes.modos_sensor
  maxLeituras.value = opcoes.max_leituras
  await carregarJobs()
})

let espera: ReturnType<typeof setTimeout> | undefined
watch(
  p,
  () => {
    clearTimeout(espera)
    espera = setTimeout(async () => {
      try {
        estimativa.value = (await estimarLab(p)).leituras
      } catch {
        estimativa.value = null
      }
    }, 250)
  },
  { deep: true, immediate: true },
)

watch(() => tempoReal.jobsMudaram, carregarJobs)

const cabe = computed(() => estimativa.value === null || estimativa.value <= maxLeituras.value)

async function gerar(): Promise<void> {
  enviando.value = true
  erro.value = null
  try {
    await gerarDados(p)
    await carregarJobs()
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  } finally {
    enviando.value = false
  }
}

function progresso(job: Job): { fracao: number; etapa: string } {
  const vivo = tempoReal.progressoJobs[job.id]
  if (vivo && job.status !== 'concluido' && job.status !== 'falhou') {
    return { fracao: Number(vivo.progresso ?? 0), etapa: String(vivo.etapa ?? '') }
  }
  return { fracao: job.status === 'concluido' ? 1 : job.progresso, etapa: job.etapa ?? '' }
}

function statusVivo(job: Job): string {
  const vivo = tempoReal.progressoJobs[job.id]
  return job.status === 'na_fila' && vivo ? String(vivo.status) : job.status
}

const ROTULO_STATUS: Record<string, string> = {
  na_fila: 'na fila', executando: 'executando', concluido: 'concluído', falhou: 'falhou',
}
</script>

<template>
  <div class="pagina">
    <p class="intro">
      Equipamento de verdade leva meses para falhar. Aqui simulamos a vida inteira de uma frota de exaustores (com o
      mesmo modelo físico do simulador) para ter exemplos suficientes para treinar a IA. O pedido entra na fila
      <code>q.jobs.gerar</code> do RabbitMQ e roda no serviço <code>lab</code>; a API responde na hora e o progresso
      chega pelo WebSocket.
    </p>

    <form class="gg-cartao" @submit.prevent="gerar">
      <h2 class="gg-titulo">Nova geração</h2>
      <p v-if="erro" class="gg-alerta gg-alerta--erro">{{ erro }}</p>

      <div class="gg-form">
        <label class="gg-campo">
          <span>Exaustores simulados</span>
          <input v-model.number="p.equipamentos" class="gg-input" type="number" min="10" max="500" />
        </label>
        <label class="gg-campo">
          <span>Período simulado (dias)</span>
          <input v-model.number="p.dias" class="gg-input" type="number" min="1" max="365" />
        </label>
        <label class="gg-campo">
          <span>Equipamentos que falham (%)</span>
          <input v-model.number="p.pct_falha" class="gg-input" type="number" min="0" max="100" />
        </label>
        <label class="gg-campo">
          <span>Semente aleatória</span>
          <input v-model.number="p.semente" class="gg-input" type="number" min="0" />
        </label>
      </div>

      <fieldset class="grupo">
        <legend>Sensores de ambiente, por tipo</legend>
        <div class="gg-form">
          <label v-for="tipo in (['gas', 'temperatura', 'umidade', 'luminosidade'] as const)" :key="tipo" class="gg-campo">
            <span>{{ { gas: 'Gás', temperatura: 'Temperatura', umidade: 'Umidade', luminosidade: 'Luminosidade' }[tipo] }}</span>
            <input v-model.number="p.sensores_ambiente[tipo]" class="gg-input" type="number" min="0" max="50" />
          </label>
        </div>
        <p class="nota">Cada exaustor tem 4 sensores: vibração, corrente, temperatura do motor e rotação.</p>
      </fieldset>

      <fieldset class="grupo">
        <legend>Modos de falha sorteados entre os que falham</legend>
        <div class="modos">
          <label v-for="m in modosEquipamento" :key="m" class="gg-checkbox">
            <input v-model="p.modos" type="checkbox" :value="m" /> {{ ROTULO_MODO[m] ?? m }}
          </label>
          <label v-for="m in modosSensor" :key="m" class="gg-checkbox sensor">
            <input v-model="p.modos" type="checkbox" :value="m" /> {{ ROTULO_MODO[m] ?? m }} <small>(o exaustor está bom)</small>
          </label>
        </div>
      </fieldset>

      <fieldset class="grupo">
        <legend>Qualidade dos dados</legend>
        <div class="gg-form">
          <label class="gg-campo">
            <span>Ruído: {{ p.ruido.toFixed(2) }}</span>
            <input v-model.number="p.ruido" type="range" min="0" max="1" step="0.05" />
          </label>
          <label class="gg-campo">
            <span>Leituras faltantes (%)</span>
            <input v-model.number="p.pct_faltantes" class="gg-input" type="number" min="0" max="20" step="0.1" />
          </label>
          <label class="gg-campo">
            <span>Valores absurdos (%)</span>
            <input v-model.number="p.pct_outliers" class="gg-input" type="number" min="0" max="10" step="0.1" />
          </label>
          <label class="gg-campo">
            <span>Amostra no InfluxDB</span>
            <span class="gg-checkbox"><input v-model="p.amostra_influx" type="checkbox" /> gravar no bucket <code>lab</code></span>
          </label>
        </div>
      </fieldset>

      <div class="estimativa" :class="{ excede: !cabe }">
        <strong>{{ estimativa === null ? '—' : fmtMil(estimativa) }}</strong> leituras (estimativa; quem falha para antes do fim)
        · teto {{ fmtMil(maxLeituras) }}
        <span v-if="!cabe"> — passa do teto: reduza máquinas, dias ou sensores</span>
        <span v-else-if="estimativa !== null && estimativa < 1_000_000"> — abaixo de 1 milhão</span>
      </div>

      <div class="gg-acoes">
        <button v-if="auth.pode('administrador')" type="submit" class="gg-btn gg-btn--primario" :disabled="enviando || !cabe">
          {{ enviando ? 'Enfileirando…' : 'Gerar dados' }}
        </button>
        <p v-else class="nota">Gerar dados é permitido ao administrador.</p>
      </div>
    </form>

    <section class="gg-cartao">
      <h2 class="gg-titulo">Datasets gerados</h2>
      <p v-if="jobs.length === 0" class="gg-vazio">Nenhum ainda.</p>
      <div v-for="job in jobs" :key="job.id" class="job" :data-status="statusVivo(job)">
        <div class="job-topo">
          <strong>ds{{ job.id }}</strong>
          <span class="status">{{ ROTULO_STATUS[statusVivo(job)] ?? statusVivo(job) }}</span>
          <span class="quando">{{ dataHora(job.criado_em) }} · {{ job.usuario }}</span>
        </div>
        <div class="barra"><div :style="{ width: `${Math.round(progresso(job).fracao * 100)}%` }" /></div>
        <p class="etapa">{{ Math.round(progresso(job).fracao * 100) }}% · {{ progresso(job).etapa }}</p>
        <p v-if="job.erro" class="gg-alerta gg-alerta--erro">{{ job.erro.length > 280 ? `${job.erro.slice(0, 280)}…` : job.erro }}</p>
        <dl v-if="job.resultado" class="resultado">
          <div><dt>Leituras</dt><dd>{{ fmtMil(job.resultado.leituras as number) }}</dd></div>
          <div><dt>Linhas de exaustor</dt><dd>{{ fmtMil(job.resultado.linhas_exaustor as number) }}</dd></div>
          <div><dt>Máquinas que falham</dt><dd>{{ job.resultado.maquinas_que_falham }}</dd></div>
          <div><dt>Tamanho</dt><dd>{{ job.resultado.tamanho_mb }} MB</dd></div>
          <div><dt>Tempo</dt><dd>{{ job.resultado.segundos }} s</dd></div>
          <div class="largo">
            <dt>Modos</dt>
            <dd>{{ Object.entries((job.resultado.modos as Record<string, number>) ?? {}).map(([m, n]) => `${ROTULO_MODO[m] ?? m}: ${n}`).join(' · ') }}</dd>
          </div>
          <div v-if="job.resultado.amostra_influx" class="largo">
            <dt>Amostra no InfluxDB (bucket lab)</dt>
            <dd>{{ (job.resultado.amostra_influx as string[]).join(', ') }} — filtre por <code>dataset = ds{{ job.id }}</code></dd>
          </div>
        </dl>
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
  max-width: 62rem;
}
code {
  font-family: var(--gg-mono);
  font-size: 0.88em;
  background: var(--gg-surface-2);
  padding: 0.05em 0.3em;
  border-radius: 3px;
}
.grupo {
  border: 1px solid var(--gg-line-soft);
  border-radius: 6px;
  margin: 1.1rem 0 0;
  padding: 0.7rem 1rem 0.9rem;
}
legend {
  font-size: 0.78rem;
  font-weight: 600;
  padding: 0 0.3rem;
}
.modos {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 0 1rem;
}
.modos .sensor small {
  color: var(--gg-ink-2);
}
.nota {
  margin: 0.4rem 0 0;
  font-size: 0.8rem;
  color: var(--gg-ink-2);
}
.estimativa {
  margin-top: 1rem;
  padding: 0.6rem 0.8rem;
  border-radius: 5px;
  background: var(--gg-surface-2);
  font-size: 0.9rem;
}
.estimativa.excede {
  background: rgba(169, 59, 44, 0.08);
  color: var(--gg-crit);
}
.job {
  border-top: 1px solid var(--gg-line-soft);
  padding: 0.8rem 0;
}
.job:first-of-type {
  border-top: none;
  padding-top: 0;
}
.job-topo {
  display: flex;
  gap: 0.7rem;
  align-items: baseline;
  flex-wrap: wrap;
}
.status {
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.job[data-status='concluido'] .status { color: var(--gg-ok); }
.job[data-status='falhou'] .status { color: var(--gg-crit); }
.job[data-status='executando'] .status { color: var(--gg-warn); }
.quando {
  font-size: 0.8rem;
  color: var(--gg-ink-2);
}
.barra {
  height: 6px;
  border-radius: 3px;
  background: var(--gg-line-soft);
  margin: 0.5rem 0 0.25rem;
  overflow: hidden;
}
.barra div {
  height: 100%;
  background: var(--gg-ok);
  transition: width 0.4s;
}
.etapa {
  margin: 0;
  font-size: 0.8rem;
  color: var(--gg-ink-2);
}
.resultado {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.5rem 1rem;
  margin: 0.6rem 0 0;
}
.resultado .largo {
  grid-column: 1 / -1;
}
.resultado dt {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--gg-ink-2);
}
.resultado dd {
  margin: 0;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
</style>
