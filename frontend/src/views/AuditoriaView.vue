<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { listarAuditoria, mensagemDeErro } from '../api/client'
import type { RegistroAuditoria } from '../api/types'
import { dataHora } from '../lib/formato'

const registros = ref<RegistroAuditoria[]>([])
const filtro = ref('')
const erro = ref<string | null>(null)

const FILTROS = [
  { valor: '', texto: 'Tudo' },
  { valor: 'login', texto: 'Logins (inclusive falhos)' },
  { valor: 'comando', texto: 'Comandos (web e regras)' },
  { valor: 'job', texto: 'Jobs (gerar, treinar)' },
  { valor: 'simulador', texto: 'Simulador' },
  { valor: 'assistente', texto: 'Perguntas ao assistente' },
  { valor: 'modelo', texto: 'Modelos' },
]

async function carregar(): Promise<void> {
  try {
    registros.value = await listarAuditoria(200, filtro.value)
    erro.value = null
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  }
}

watch(filtro, carregar)
onMounted(carregar)
</script>

<template>
  <div class="pagina">
    <p class="intro">
      Tabela <code>auditoria</code> do PostgreSQL: só recebe INSERT. Logins (e tentativas que falharam), comandos
      enviados pela web e pelas regras, jobs disparados, perguntas ao assistente e mudanças de cadastro.
    </p>
    <div class="barra">
      <select v-model="filtro" class="gg-select">
        <option v-for="f in FILTROS" :key="f.valor" :value="f.valor">{{ f.texto }}</option>
      </select>
      <button type="button" class="gg-btn" @click="carregar">Atualizar</button>
    </div>
    <p v-if="erro" class="gg-alerta gg-alerta--erro">{{ erro }}</p>
    <section class="gg-cartao gg-rolagem">
      <table class="gg-tabela">
        <thead><tr><th>Quando</th><th>Usuário</th><th>Ação</th><th>Detalhe</th><th>IP</th><th></th></tr></thead>
        <tbody>
          <tr v-for="r in registros" :key="r.id" :class="{ falha: !r.sucesso }">
            <td class="gg-num">{{ dataHora(r.instante) }}</td>
            <td>{{ r.usuario ?? 'sistema' }} <small v-if="r.papel">{{ r.papel }}</small></td>
            <td><code>{{ r.acao }}</code></td>
            <td class="detalhe">{{ JSON.stringify(r.detalhe) }}</td>
            <td class="gg-num">{{ r.ip ?? '—' }}</td>
            <td>{{ r.sucesso ? '' : 'falhou' }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.pagina {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.intro {
  margin: 0;
  color: var(--gg-ink-2);
}
code {
  font-family: var(--gg-mono);
  font-size: 0.85em;
}
.barra {
  display: flex;
  gap: 0.5rem;
}
.barra .gg-select {
  width: auto;
}
small {
  color: var(--gg-ink-2);
}
.detalhe {
  font-family: var(--gg-mono);
  font-size: 0.75rem;
  color: var(--gg-ink-2);
  max-width: 34rem;
  word-break: break-word;
}
tr.falha td {
  color: var(--gg-crit);
}
</style>
