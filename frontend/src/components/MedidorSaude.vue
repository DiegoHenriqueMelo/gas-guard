<script setup lang="ts">
// Semicirculo de 0 a 100 para o indice de saude previsto pela IA.
import { computed } from 'vue'

import { COR_ESTADO } from '../lib/estado'

const props = withDefaults(defineProps<{ valor: number | null; tamanho?: number }>(), { tamanho: 170 })

const RAIO = 70
const COMPRIMENTO = Math.PI * RAIO

const cor = computed(() => {
  if (props.valor === null) return COR_ESTADO.sem_dados
  if (props.valor < 30) return COR_ESTADO.critico
  if (props.valor < 60) return COR_ESTADO.atencao
  return COR_ESTADO.normal
})

const preenchido = computed(() => (COMPRIMENTO * Math.max(0, Math.min(100, props.valor ?? 0))) / 100)
</script>

<template>
  <svg :width="tamanho" :height="tamanho * 0.62" viewBox="0 0 180 112" role="img"
       :aria-label="valor === null ? 'saúde sem previsão' : `saúde ${valor.toFixed(0)} de 100`">
    <path d="M 20 95 A 70 70 0 0 1 160 95" fill="none" stroke="var(--gg-line-soft)" stroke-width="14"
          stroke-linecap="round" />
    <path d="M 20 95 A 70 70 0 0 1 160 95" fill="none" :stroke="cor" stroke-width="14" stroke-linecap="round"
          :stroke-dasharray="`${preenchido} ${COMPRIMENTO}`" style="transition: stroke-dasharray 0.6s" />
    <text x="90" y="84" text-anchor="middle" class="valor">{{ valor === null ? '—' : valor.toFixed(0) }}</text>
    <text x="90" y="104" text-anchor="middle" class="rotulo">saúde / 100</text>
  </svg>
</template>

<style scoped>
.valor {
  font-size: 34px;
  font-weight: 650;
  fill: var(--gg-ink);
  font-variant-numeric: tabular-nums;
}
.rotulo {
  font-size: 11px;
  fill: var(--gg-ink-2);
  letter-spacing: 0.06em;
}
</style>
