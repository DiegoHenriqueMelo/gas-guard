<script setup lang="ts">
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from 'chart.js'
import { computed } from 'vue'
import { Line } from 'vue-chartjs'

import { LIMITE_ATENCAO, LIMITE_CRITICO, type Leitura } from '../api/types'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Filler,
)

const props = defineProps<{ leituras: Leitura[] }>()

function hora(iso: string): string {
  return new Date(iso).toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

// Sem o plugin de anotacoes, as faixas viram datasets planos: um valor
// constante repetido em todos os pontos do eixo x.
function linhaConstante(valor: number, tamanho: number): number[] {
  return new Array(tamanho).fill(valor)
}

const dados = computed<ChartData<'line'>>(() => {
  const total = props.leituras.length

  return {
    labels: props.leituras.map((leitura) => hora(leitura.horario)),
    datasets: [
      {
        label: 'ppm',
        data: props.leituras.map((leitura) => leitura.ppm),
        borderColor: '#0b6e75',
        backgroundColor: 'rgba(11, 110, 117, 0.12)',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.25,
        fill: true,
      },
      {
        label: 'Atenção',
        data: linhaConstante(LIMITE_ATENCAO, total),
        borderColor: 'rgba(169, 116, 26, 0.7)',
        borderWidth: 1,
        borderDash: [6, 4],
        pointRadius: 0,
        fill: false,
      },
      {
        label: 'Crítico',
        data: linhaConstante(LIMITE_CRITICO, total),
        borderColor: 'rgba(169, 59, 44, 0.75)',
        borderWidth: 1,
        borderDash: [6, 4],
        pointRadius: 0,
        fill: false,
      },
    ],
  }
})

const opcoes = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      filter: (item) => item.datasetIndex === 0,
      callbacks: {
        label: (item) => `${Number(item.parsed.y).toFixed(0)} ppm`,
      },
    },
  },
  scales: {
    x: {
      ticks: { maxTicksLimit: 8, color: '#6b7d7c', maxRotation: 0 },
      grid: { display: false },
    },
    y: {
      beginAtZero: true,
      suggestedMax: LIMITE_CRITICO * 1.3,
      ticks: { color: '#6b7d7c' },
      grid: { color: 'rgba(15, 29, 28, 0.07)' },
      title: { display: true, text: 'ppm', color: '#6b7d7c' },
    },
  },
}))
</script>

<template>
  <div class="grafico">
    <p v-if="leituras.length === 0" class="vazio">
      Nenhuma leitura no período selecionado.
    </p>
    <Line v-else :data="dados" :options="opcoes" />
  </div>
</template>

<style scoped>
.grafico {
  height: 320px;
  position: relative;
}

.vazio {
  display: grid;
  place-items: center;
  height: 100%;
  margin: 0;
  color: var(--gg-ink-2);
  font-size: 0.95rem;
}
</style>
