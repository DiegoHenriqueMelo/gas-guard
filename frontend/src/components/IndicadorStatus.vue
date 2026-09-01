<script setup lang="ts">
import { computed } from 'vue'

import {
  ROTULO_NIVEL,
  classificar,
  type Dispositivo,
  type Leitura,
  type Nivel,
} from '../api/types'

const props = defineProps<{
  dispositivo: Dispositivo | null
  leituras: Leitura[]
}>()

const ultima = computed<Leitura | null>(
  () => props.leituras[props.leituras.length - 1] ?? null,
)

const nivel = computed<Nivel | null>(() =>
  ultima.value ? classificar(ultima.value.ppm) : null,
)

const maxima = computed<number | null>(() => {
  if (props.leituras.length === 0) return null
  return Math.max(...props.leituras.map((leitura) => leitura.ppm))
})

const media = computed<number | null>(() => {
  if (props.leituras.length === 0) return null
  const soma = props.leituras.reduce((total, leitura) => total + leitura.ppm, 0)
  return soma / props.leituras.length
})

const ultimoContato = computed<string>(() => {
  const iso = props.dispositivo?.ultimo_contato
  if (!iso) return 'nunca reportou'

  const segundos = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (segundos < 10) return 'agora mesmo'
  if (segundos < 60) return `há ${segundos}s`
  if (segundos < 3600) return `há ${Math.floor(segundos / 60)} min`
  return new Date(iso).toLocaleString('pt-BR')
})

function formatar(valor: number | null): string {
  return valor === null ? '—' : valor.toFixed(0)
}
</script>

<template>
  <section class="indicador" :data-nivel="nivel ?? 'sem-dado'">
    <header class="topo">
      <div>
        <p class="rotulo">Concentração atual</p>
        <p class="valor">
          {{ formatar(ultima?.ppm ?? null) }}<span class="unidade">ppm</span>
        </p>
      </div>
      <span class="selo">{{ nivel ? ROTULO_NIVEL[nivel] : 'Sem dado' }}</span>
    </header>

    <dl class="resumo">
      <div>
        <dt>Máxima no período</dt>
        <dd>{{ formatar(maxima) }} ppm</dd>
      </div>
      <div>
        <dt>Média no período</dt>
        <dd>{{ formatar(media) }} ppm</dd>
      </div>
      <div>
        <dt>Último contato</dt>
        <dd>{{ ultimoContato }}</dd>
      </div>
      <div>
        <dt>Leituras recebidas</dt>
        <dd>{{ leituras.length }}</dd>
      </div>
    </dl>
  </section>
</template>

<style scoped>
.indicador {
  border: 1px solid var(--gg-line);
  border-left: 4px solid var(--gg-ink-2);
  border-radius: 6px;
  background: var(--gg-surface);
  padding: 1.25rem 1.4rem;
  box-shadow: var(--gg-shadow);
}

.indicador[data-nivel='normal'] {
  border-left-color: var(--gg-ok);
}
.indicador[data-nivel='atencao'] {
  border-left-color: var(--gg-warn);
}
.indicador[data-nivel='critico'] {
  border-left-color: var(--gg-crit);
  animation: pulsa 1.4s ease-in-out infinite;
}

@keyframes pulsa {
  50% {
    background: rgba(169, 59, 44, 0.07);
  }
}

@media (prefers-reduced-motion: reduce) {
  .indicador[data-nivel='critico'] {
    animation: none;
    background: rgba(169, 59, 44, 0.07);
  }
}

.topo {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.rotulo {
  margin: 0;
  font-size: 0.78rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--gg-ink-2);
}

.valor {
  margin: 0.15rem 0 0;
  font-size: 2.7rem;
  font-weight: 600;
  line-height: 1.05;
  color: var(--gg-ink);
  font-variant-numeric: tabular-nums;
}

.unidade {
  font-size: 1rem;
  font-weight: 500;
  color: var(--gg-ink-2);
  margin-left: 0.35rem;
}

.selo {
  padding: 0.3rem 0.7rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
  border: 1px solid currentColor;
  white-space: nowrap;
}

.indicador[data-nivel='normal'] .selo {
  color: var(--gg-ok);
}
.indicador[data-nivel='atencao'] .selo {
  color: var(--gg-warn);
}
.indicador[data-nivel='critico'] .selo {
  color: var(--gg-crit);
}
.indicador[data-nivel='sem-dado'] .selo {
  color: var(--gg-ink-2);
}

.resumo {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.9rem 1.4rem;
  margin: 1.3rem 0 0;
  padding-top: 1.1rem;
  border-top: 1px solid var(--gg-line-soft);
}

.resumo dt {
  font-size: 0.74rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--gg-ink-2);
}

.resumo dd {
  margin: 0.2rem 0 0;
  font-size: 1.02rem;
  font-weight: 500;
  color: var(--gg-ink);
  font-variant-numeric: tabular-nums;
}
</style>
