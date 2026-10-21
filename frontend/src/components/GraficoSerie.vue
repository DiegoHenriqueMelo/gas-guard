<script setup lang="ts">
// Grafico de linha generico (Chart.js): uma ou mais series no tempo, com
// linhas de limite opcionais (faixa de atencao/critico).
import {
  Chart as ChartJS,
  Filler,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  Legend,
  type ChartData,
  type ChartOptions,
} from 'chart.js'
import { computed } from 'vue'
import { Line } from 'vue-chartjs'

import { hora } from '../lib/formato'

ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Filler, Legend)

export interface SerieGrafico {
  rotulo: string
  cor: string
  pontos: { x: number; y: number }[]
  preencher?: boolean
}

const props = withDefaults(
  defineProps<{
    series: SerieGrafico[]
    unidade?: string
    limites?: { valor: number; rotulo: string; cor: string }[]
    altura?: number
    minY?: number
    maxY?: number
  }>(),
  { unidade: '', limites: () => [], altura: 280 },
)

const vazio = computed(() => props.series.every((s) => s.pontos.length === 0))

const intervaloMs = computed(() => {
  const xs = props.series.flatMap((s) => s.pontos.map((p) => p.x))
  return xs.length ? Math.max(...xs) - Math.min(...xs) : 0
})

/**
 * Quebra a linha onde faltou dado (simulador parado, servico reiniciado):
 * sem isto o Chart.js liga os dois lados com uma reta que parece leitura.
 * Buraco = intervalo maior que 5x o intervalo tipico (e no minimo 30 s).
 */
function comBuracos(pontos: { x: number; y: number }[]): { x: number; y: number | null }[] {
  if (pontos.length < 3) return pontos
  const passos = pontos.slice(1).map((p, i) => p.x - pontos[i].x).sort((a, b) => a - b)
  const limite = Math.max(30_000, 5 * passos[Math.floor(passos.length / 2)])
  const saida: { x: number; y: number | null }[] = [pontos[0]]
  for (let i = 1; i < pontos.length; i++) {
    if (pontos[i].x - pontos[i - 1].x > limite) saida.push({ x: pontos[i - 1].x + 1, y: null })
    saida.push(pontos[i])
  }
  return saida
}

const dados = computed<ChartData<'line'>>(() => {
  const xs = props.series.flatMap((s) => s.pontos.map((p) => p.x))
  const inicio = Math.min(...xs)
  const fim = Math.max(...xs)
  return {
    datasets: [
      ...props.series.map((s) => ({
        label: s.rotulo,
        data: comBuracos(s.pontos),
        borderColor: s.cor,
        backgroundColor: `${s.cor}22`,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.25,
        fill: s.preencher ?? props.series.length === 1,
      })),
      // sem plugin de anotacoes: o limite vira uma serie de dois pontos
      ...props.limites.map((l) => ({
        label: l.rotulo,
        data: [{ x: inicio, y: l.valor }, { x: fim, y: l.valor }],
        borderColor: l.cor,
        borderWidth: 1,
        borderDash: [6, 4],
        pointRadius: 0,
        fill: false,
      })),
    ],
  }
})

const opcoes = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  parsing: false,
  interaction: { mode: 'nearest', axis: 'x', intersect: false },
  plugins: {
    legend: { display: props.series.length > 1, labels: { boxWidth: 12, color: '#556e6c' } },
    tooltip: {
      callbacks: {
        title: (itens) => (itens[0] ? hora(itens[0].parsed.x ?? 0) : ''),
        label: (item) => `${item.dataset.label}: ${Number(item.parsed.y).toFixed(1)} ${props.unidade}`,
      },
    },
  },
  scales: {
    x: {
      type: 'linear',
      ticks: {
        maxTicksLimit: 7,
        color: '#6b7d7c',
        // periodo curto (ao vivo): hh:mm:ss; longo: hh:mm
        callback: (v) => hora(Number(v)).slice(0, intervaloMs.value < 15 * 60_000 ? 8 : 5),
      },
      grid: { display: false },
    },
    y: {
      min: props.minY,
      max: props.maxY,
      ticks: { color: '#6b7d7c' },
      grid: { color: 'rgba(15, 29, 28, 0.07)' },
      title: { display: Boolean(props.unidade), text: props.unidade, color: '#6b7d7c' },
    },
  },
}))
</script>

<template>
  <div class="grafico" :style="{ height: `${altura}px` }">
    <p v-if="vazio" class="vazio">Sem leituras no período.</p>
    <Line v-else :data="dados" :options="opcoes" />
  </div>
</template>

<style scoped>
.grafico {
  position: relative;
}
.vazio {
  display: grid;
  place-items: center;
  height: 100%;
  margin: 0;
  color: var(--gg-ink-2);
}
</style>
