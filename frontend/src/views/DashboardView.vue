<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { buscarHistorico, listarAmbientes, listarDispositivos } from '../api/client'
import type { Ambiente, Dispositivo, Leitura } from '../api/types'
import GraficoLeituras from '../components/GraficoLeituras.vue'
import IndicadorStatus from '../components/IndicadorStatus.vue'

const INTERVALO_ATUALIZACAO = 5000

const ambientes = ref<Ambiente[]>([])
const dispositivos = ref<Dispositivo[]>([])
const leituras = ref<Leitura[]>([])

const codigoSelecionado = ref('')
const minutos = ref(30)
const erro = ref<string | null>(null)
const carregandoInicial = ref(true)

let temporizador: ReturnType<typeof setInterval> | undefined

const dispositivo = computed<Dispositivo | null>(
  () => dispositivos.value.find((d) => d.codigo === codigoSelecionado.value) ?? null,
)

const nomeAmbiente = computed<string>(() => {
  const id = dispositivo.value?.ambiente_id
  return ambientes.value.find((a) => a.id === id)?.nome ?? '—'
})

function descreverErro(causa: unknown): string {
  if (causa instanceof Error) return causa.message
  return 'Falha ao falar com a API'
}

async function carregarCadastro(): Promise<void> {
  try {
    const [listaAmbientes, listaDispositivos] = await Promise.all([
      listarAmbientes(),
      listarDispositivos(),
    ])

    ambientes.value = listaAmbientes
    dispositivos.value = listaDispositivos

    if (!codigoSelecionado.value && listaDispositivos.length > 0) {
      codigoSelecionado.value = listaDispositivos[0].codigo
    }

    erro.value = null
  } catch (causa) {
    erro.value = descreverErro(causa)
  }
}

async function carregarLeituras(): Promise<void> {
  if (!codigoSelecionado.value) {
    leituras.value = []
    return
  }

  try {
    leituras.value = await buscarHistorico(codigoSelecionado.value, minutos.value)
    erro.value = null
  } catch (causa) {
    erro.value = descreverErro(causa)
  }
}

async function atualizar(): Promise<void> {
  await Promise.all([carregarCadastro(), carregarLeituras()])
}

watch([codigoSelecionado, minutos], carregarLeituras)

onMounted(async () => {
  await carregarCadastro()
  await carregarLeituras()
  carregandoInicial.value = false

  temporizador = setInterval(atualizar, INTERVALO_ATUALIZACAO)
})

// Sem isto o intervalo continua rodando depois de sair da rota e vira
// vazamento de memoria com requisicao de brinde a cada 5 segundos.
onUnmounted(() => clearInterval(temporizador))
</script>

<template>
  <div class="painel">
    <section class="controles">
      <label>
        <span>Dispositivo</span>
        <select v-model="codigoSelecionado" :disabled="dispositivos.length === 0">
          <option v-for="item in dispositivos" :key="item.id" :value="item.codigo">
            {{ item.nome }} ({{ item.codigo }})
          </option>
        </select>
      </label>

      <label>
        <span>Período</span>
        <select v-model.number="minutos">
          <option :value="5">Últimos 5 minutos</option>
          <option :value="30">Últimos 30 minutos</option>
          <option :value="60">Última hora</option>
          <option :value="360">Últimas 6 horas</option>
          <option :value="1440">Últimas 24 horas</option>
        </select>
      </label>

      <p class="ambiente">
        <span>Ambiente</span>
        <strong>{{ nomeAmbiente }}</strong>
      </p>
    </section>

    <p v-if="erro" class="erro">{{ erro }}</p>

    <p v-if="carregandoInicial" class="carregando">Carregando…</p>

    <template v-else-if="dispositivos.length === 0">
      <p class="carregando">
        Nenhum dispositivo cadastrado. Cadastre um em
        <code>POST /api/dispositivos</code> com o mesmo código do firmware.
      </p>
    </template>

    <template v-else>
      <IndicadorStatus :dispositivo="dispositivo" :leituras="leituras" />

      <section class="cartao">
        <h2>Concentração ao longo do tempo</h2>
        <GraficoLeituras :leituras="leituras" />
      </section>
    </template>
  </div>
</template>

<style scoped>
.painel {
  display: flex;
  flex-direction: column;
  gap: 1.4rem;
}

.controles {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1rem 1.6rem;
}

.controles label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.controles span {
  font-size: 0.74rem;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--gg-ink-2);
}

.controles select {
  font: inherit;
  font-size: 0.95rem;
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--gg-line);
  border-radius: 5px;
  background: var(--gg-surface);
  color: var(--gg-ink);
  min-width: 15rem;
}

.ambiente {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin: 0;
}

.ambiente strong {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--gg-ink);
  padding: 0.5rem 0;
}

.cartao {
  border: 1px solid var(--gg-line);
  border-radius: 6px;
  background: var(--gg-surface);
  padding: 1.25rem 1.4rem 1.5rem;
  box-shadow: var(--gg-shadow);
}

.cartao h2 {
  margin: 0 0 1rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--gg-ink);
}

.erro {
  margin: 0;
  padding: 0.8rem 1rem;
  border: 1px solid var(--gg-crit);
  border-radius: 5px;
  background: rgba(169, 59, 44, 0.08);
  color: var(--gg-crit);
  font-size: 0.92rem;
}

.carregando {
  margin: 0;
  color: var(--gg-ink-2);
}

code {
  font-family: var(--gg-mono);
  font-size: 0.88em;
  background: var(--gg-surface-2);
  padding: 0.1em 0.35em;
  border-radius: 3px;
}
</style>
