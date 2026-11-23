<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { comandarSimulador, mensagemDeErro } from '../api/client'
import type { Estado } from '../api/types'
import BotoesComando from '../components/BotoesComando.vue'
import MiniGrafico from '../components/MiniGrafico.vue'
import SeloEstado from '../components/SeloEstado.vue'
import { CenaCozinha, type DadosQuadro } from '../cena/CenaCozinha'
import { COR_ESTADO, estadoDoDispositivo } from '../lib/estado'
import { fmt, haQuanto, ROTULO_CAMPO, UNIDADE_CAMPO } from '../lib/formato'
import { useAuth } from '../stores/auth'
import { useCadastro } from '../stores/cadastro'
import { useTempoReal } from '../stores/tempoReal'

const auth = useAuth()
const cadastro = useCadastro()
const tempoReal = useTempoReal()

const palco = ref<HTMLDivElement | null>(null)
const selecionado = ref<string | null>(null)
let cena: CenaCozinha | null = null

/** Chamada pela cena A CADA QUADRO: le o store cru, sem reatividade. */
function lerQuadro(): DadosQuadro {
  const itens: DadosQuadro['itens'] = {}
  for (const d of cadastro.ativos) {
    const leitura = tempoReal.bruto.telemetria[d.codigo]
    const insight = tempoReal.bruto.insights[d.codigo]
    itens[d.codigo] = {
      estado: estadoDoDispositivo(d, leitura, insight, cadastro.alertas, tempoReal.semDados(d.codigo)),
      leitura,
      insight,
    }
  }
  return { semDados: tempoReal.semDados(), itens }
}

onMounted(() => {
  if (!palco.value) return
  cena = new CenaCozinha(palco.value, lerQuadro, (codigo) => (selecionado.value = codigo))
  cena.definirDispositivos(cadastro.ativos)
})
onUnmounted(() => cena?.destruir())

// so recria os objetos quando o CADASTRO muda, nunca por causa de leitura
watch(
  () => cadastro.ativos.map((d) => d.codigo).join(','),
  () => cena?.definirDispositivos(cadastro.ativos),
)

const semDados = computed(() => {
  void tempoReal.versao
  return tempoReal.semDados()
})

// ---------- painel do item clicado ----------
function fecharPainel(): void {
  cena?.selecionar(null)
}

const dispositivo = computed(() => (selecionado.value ? cadastro.porCodigo[selecionado.value] : undefined))
const leitura = computed(() => {
  void tempoReal.versao
  return selecionado.value ? tempoReal.bruto.telemetria[selecionado.value] : undefined
})
const insight = computed(() => {
  void tempoReal.versao
  return selecionado.value ? tempoReal.bruto.insights[selecionado.value] : undefined
})
const estado = computed<Estado>(() => {
  void tempoReal.versao
  const d = dispositivo.value
  if (!d) return 'sem_dados'
  return estadoDoDispositivo(d, leitura.value, insight.value, cadastro.alertas, tempoReal.semDados(d.codigo))
})
const campoGrafico = computed(() => {
  const d = dispositivo.value
  if (!d) return null
  return d.categoria === 'atuador' ? 'acionado' : d.campo_principal
})
const serie = computed(() => {
  void tempoReal.versao
  const d = dispositivo.value
  if (!d || !campoGrafico.value) return []
  return [...(tempoReal.bruto.series[d.codigo]?.[campoGrafico.value]?.v ?? [])]
})
const serieSaude = computed(() => {
  void tempoReal.versao
  return selecionado.value ? [...(tempoReal.bruto.seriesSaude[selecionado.value]?.v ?? [])] : []
})
const alertasDoItem = computed(() => cadastro.alertas.filter((a) => a.dispositivo_codigo === selecionado.value))

// ---------- falha no exaustor (simulador) ----------
const modo = ref('rolamento')
const retorno = ref<string | null>(null)
async function simular(comando: Record<string, unknown>, texto: string): Promise<void> {
  try {
    await comandarSimulador(comando)
    retorno.value = `${texto}: enviado.`
  } catch (causa) {
    retorno.value = mensagemDeErro(causa)
  }
}
</script>

<template>
  <div class="gemeo">
    <div ref="palco" class="palco">
      <div v-if="semDados" class="sem-dados">
        <strong>Sem dados em tempo real</strong>
        <span>Nenhuma leitura chegou pelo WebSocket nos últimos 8 segundos. O simulador está parado?</span>
      </div>
      <div class="legenda">
        <span v-for="e in (['normal', 'atencao', 'critico', 'sem_dados'] as Estado[])" :key="e">
          <i :style="{ background: COR_ESTADO[e] }" /> {{ { normal: 'normal', atencao: 'atenção', critico: 'crítico', sem_dados: 'sem dados' }[e] }}
        </span>
      </div>
      <p class="dica">Arraste para girar · role para aproximar · clique num item</p>
    </div>

    <aside v-if="dispositivo" class="painel gg-cartao">
      <div class="painel-topo">
        <div>
          <h2>{{ dispositivo.nome }}</h2>
          <p class="codigo">{{ dispositivo.codigo }} · {{ dispositivo.categoria }}</p>
        </div>
        <button type="button" class="fechar" aria-label="Fechar" @click="fecharPainel">×</button>
      </div>
      <SeloEstado :estado="estado" />

      <dl class="leituras">
        <div v-for="(valor, campo) in leitura?.leituras ?? {}" :key="campo">
          <dt>{{ ROTULO_CAMPO[campo] ?? campo }}</dt>
          <dd>{{ fmt(valor, campo === 'ppm' || campo === 'rpm' || campo === 'lux' ? 0 : 2) }} {{ UNIDADE_CAMPO[campo] ?? '' }}</dd>
        </div>
        <div v-if="leitura?.estado">
          <dt>Estado</dt>
          <dd>{{ leitura.estado }}</dd>
        </div>
      </dl>
      <p class="quando">Última leitura {{ haQuanto(leitura?.instante) }}</p>

      <div v-if="serie.length > 1">
        <p class="rotulo-mini">{{ ROTULO_CAMPO[campoGrafico ?? ''] ?? campoGrafico }} (últimos minutos)</p>
        <MiniGrafico :valores="serie" :cor="COR_ESTADO[estado]" :altura="56" />
      </div>

      <template v-if="dispositivo.categoria === 'equipamento'">
        <div class="ia">
          <p class="rotulo-mini">Previsão da IA {{ insight?.versao_modelo ? `(modelo ${insight.versao_modelo})` : '' }}</p>
          <template v-if="insight?.estado_ia === 'ok'">
            <p class="saude">
              <strong>{{ fmt(insight.saude, 0) }}</strong>/100 de saúde ·
              <strong>{{ fmt(insight.rul_horas, 0) }} h</strong> de vida útil
            </p>
            <p class="tendencia">Tendência: {{ insight.tendencia }} ({{ fmt(insight.inclinacao_saude, 1) }} pontos/h)</p>
            <MiniGrafico v-if="serieSaude.length > 1" :valores="serieSaude" :cor="COR_ESTADO[estado]" :altura="44" />
          </template>
          <p v-else class="tendencia">
            {{ { aquecendo: `Juntando leituras (faltam ${insight?.faltam ?? '?'})`, sem_modelo: 'Nenhum modelo treinado ainda', parado: 'Motor parado: sem previsão', falha: 'Equipamento em falha' }[insight?.estado_ia ?? 'sem_modelo'] ?? '—' }}
          </p>
        </div>
      </template>

      <ul v-if="alertasDoItem.length" class="alertas">
        <li v-for="a in alertasDoItem" :key="a.id" :data-severidade="a.severidade">{{ a.mensagem }}</li>
      </ul>

      <BotoesComando
        v-if="dispositivo.controlavel"
        :codigo="dispositivo.codigo"
        :tipo="dispositivo.tipo"
        :estado="leitura?.estado ?? null"
      />

      <div v-if="dispositivo.tipo === 'exaustor' && auth.pode('operador')" class="falha">
        <p class="rotulo-mini">Simulador: falha no exaustor</p>
        <div class="linha">
          <select v-model="modo" class="gg-select">
            <option value="rolamento">Desgaste de rolamento</option>
            <option value="desbalanceamento">Desbalanceamento</option>
            <option value="entupimento">Filtro entupido</option>
            <option value="superaquecimento">Superaquecimento</option>
            <option value="deriva_sensor">Deriva de sensor</option>
            <option value="travamento_sensor">Sensor travado</option>
          </select>
          <button type="button" class="gg-btn gg-btn--mini gg-btn--perigo"
                  @click="simular({ acao: 'injetar_falha', equipamento: dispositivo.codigo, modo, horas_ate_falha: 20, progresso_inicial: 0.35 }, 'Falha injetada')">
            Injetar
          </button>
          <button type="button" class="gg-btn gg-btn--mini"
                  @click="simular({ acao: 'reparar', equipamento: dispositivo.codigo }, 'Reparo')">
            Reparar
          </button>
        </div>
        <p v-if="retorno" class="quando">{{ retorno }}</p>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.gemeo {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  height: calc(100vh - 8rem);
  min-height: 480px;
}
.palco {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--gg-line);
  background: #e9eeed;
}
.palco :deep(canvas) {
  display: block;
}
.palco :deep(.cena-rotulos) {
  position: absolute;
  top: 0;
  left: 0;
}
.palco :deep(.cena-rotulo) {
  font: 600 11px var(--gg-sans);
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  border: 1.5px solid var(--gg-ink-2);
  color: var(--gg-ink);
  white-space: nowrap;
  cursor: pointer;
  pointer-events: auto;
}
.palco :deep(.cena-rotulo[data-estado='normal']) { border-color: #2e8a5f; }
.palco :deep(.cena-rotulo[data-estado='atencao']) { border-color: #c98a1b; background: #fff6e3; }
.palco :deep(.cena-rotulo[data-estado='critico']) { border-color: #c0392b; background: #fdeceb; }
.palco :deep(.cena-rotulo[data-estado='sem_dados']) { border-color: #8a9896; color: #6b7d7c; }
.sem-dados {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  background: rgba(18, 32, 31, 0.55);
  color: #fff;
  text-align: center;
  padding: 1rem;
  pointer-events: none;
}
.sem-dados strong {
  font-size: 1.3rem;
}
.legenda {
  position: absolute;
  left: 0.8rem;
  bottom: 0.7rem;
  z-index: 2;
  display: flex;
  gap: 0.8rem;
  padding: 0.35rem 0.7rem;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 6px;
  font-size: 0.75rem;
}
.legenda i {
  display: inline-block;
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 50%;
  margin-right: 0.25rem;
  vertical-align: -1px;
}
.dica {
  position: absolute;
  right: 0.8rem;
  bottom: 0.7rem;
  z-index: 2;
  margin: 0;
  font-size: 0.72rem;
  color: var(--gg-ink-2);
  background: rgba(255, 255, 255, 0.8);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}
.painel {
  width: 20rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}
.painel-topo {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
}
.painel h2 {
  margin: 0;
  font-size: 1.05rem;
}
.codigo {
  margin: 0.1rem 0 0;
  font-size: 0.78rem;
  color: var(--gg-ink-2);
}
.fechar {
  border: none;
  background: none;
  font-size: 1.4rem;
  line-height: 1;
  cursor: pointer;
  color: var(--gg-ink-2);
}
.leituras {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.4rem 0.8rem;
  margin: 0;
}
.leituras dt,
.rotulo-mini {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--gg-ink-2);
  margin: 0 0 0.2rem;
}
.leituras dd {
  margin: 0;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.quando,
.tendencia {
  margin: 0;
  font-size: 0.8rem;
  color: var(--gg-ink-2);
}
.ia {
  border-top: 1px solid var(--gg-line-soft);
  padding-top: 0.6rem;
}
.saude {
  margin: 0 0 0.2rem;
}
.saude strong {
  font-size: 1.15rem;
}
.alertas {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.82rem;
}
.alertas li {
  padding: 0.35rem 0.5rem;
  border-radius: 4px;
  background: var(--gg-surface-2);
  border-left: 3px solid var(--gg-warn);
}
.alertas li[data-severidade='critico'] {
  border-left-color: var(--gg-crit);
}
.falha {
  border-top: 1px solid var(--gg-line-soft);
  padding-top: 0.6rem;
}
.linha {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.linha .gg-select {
  width: auto;
  flex: 1;
  font-size: 0.85rem;
}

@media (max-width: 900px) {
  .gemeo {
    grid-template-columns: 1fr;
    height: auto;
  }
  .palco {
    height: 65vh;
  }
  .painel {
    width: auto;
  }
}
</style>
