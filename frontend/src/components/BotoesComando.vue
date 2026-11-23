<script setup lang="ts">
// Botoes Web -> IoT. So aparecem para operador ou administrador; mesmo
// assim, quem decide de verdade e o backend (403 para o visualizador).
import { computed, ref } from 'vue'

import { comandar, mensagemDeErro } from '../api/client'
import { ACOES_POR_TIPO, ROTULO_ACAO } from '../lib/formato'
import { useAuth } from '../stores/auth'

const props = defineProps<{ codigo: string; tipo: string; estado: string | null }>()

const auth = useAuth()
const enviando = ref<string | null>(null)
const retorno = ref<{ ok: boolean; texto: string } | null>(null)

const acoes = computed(() => ACOES_POR_TIPO[props.tipo] ?? [])

// a acao que levaria ao estado em que o atuador ja esta fica desabilitada
const ESTADO_DA_ACAO: Record<string, string> = {
  ligar: 'ligado', desligar: 'desligado', abrir: 'aberta', fechar: 'fechada',
}

async function enviar(acao: string): Promise<void> {
  enviando.value = acao
  retorno.value = null
  try {
    await comandar(props.codigo, acao)
    retorno.value = { ok: true, texto: `${ROTULO_ACAO[acao]}: enviado. O estado muda na próxima leitura.` }
  } catch (causa) {
    retorno.value = { ok: false, texto: mensagemDeErro(causa) }
  } finally {
    enviando.value = null
  }
}
</script>

<template>
  <div v-if="acoes.length" class="comandos">
    <template v-if="auth.pode('operador')">
      <div class="botoes">
        <button
          v-for="acao in acoes"
          :key="acao"
          type="button"
          class="gg-btn gg-btn--mini"
          :class="{ 'gg-btn--primario': ESTADO_DA_ACAO[acao] !== estado }"
          :disabled="enviando !== null || ESTADO_DA_ACAO[acao] === estado || estado === 'falha'"
          @click="enviar(acao)"
        >
          {{ enviando === acao ? 'Enviando…' : ROTULO_ACAO[acao] }}
        </button>
      </div>
      <p v-if="estado === 'falha'" class="nota">Em falha: precisa de reparo antes de ligar.</p>
      <p v-if="retorno" class="nota" :class="{ erro: !retorno.ok }">{{ retorno.texto }}</p>
    </template>
    <p v-else class="nota">Comandos disponíveis para operador e administrador.</p>
  </div>
</template>

<style scoped>
.botoes {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.nota {
  margin: 0.45rem 0 0;
  font-size: 0.8rem;
  color: var(--gg-ink-2);
}
.nota.erro {
  color: var(--gg-crit);
}
</style>
