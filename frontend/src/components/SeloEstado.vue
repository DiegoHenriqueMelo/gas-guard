<script setup lang="ts">
import { ROTULO_ESTADO, type Estado } from '../api/types'

defineProps<{ estado: Estado; texto?: string }>()
</script>

<template>
  <span class="selo" :data-estado="estado">{{ texto ?? ROTULO_ESTADO[estado] }}</span>
</template>

<style scoped>
.selo {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.12rem 0.55rem;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 600;
  white-space: nowrap;
  border: 1px solid currentColor;
}
.selo::before {
  content: '';
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 50%;
  background: currentColor;
}
.selo[data-estado='normal'] { color: var(--gg-ok); }
.selo[data-estado='atencao'] { color: var(--gg-warn); }
.selo[data-estado='critico'] { color: var(--gg-crit); }
.selo[data-estado='sem_dados'] { color: var(--gg-ink-2); }
</style>
