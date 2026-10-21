<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'

import { api, mensagemDeErro, perguntar, statusAssistente } from '../api/client'
import TextoMarkdown from '../components/TextoMarkdown.vue'

interface Mensagem {
  role: 'user' | 'assistant'
  content: string
  erro?: boolean
}

const SUGESTOES = [
  'Qual equipamento está com a pior saúde agora?',
  'O que significa o alerta do exaustor e o que devo fazer?',
  'Explique as métricas do último treino em palavras simples.',
  'Como uma leitura do sensor de gás chega até esta tela?',
  'Por que usar RabbitMQ além do Mosquitto?',
]

const conversa = ref<Mensagem[]>([])
const pergunta = ref('')
const respondendo = ref(false)
const esperandoPrimeiro = ref(false)
const status = ref<{ modelo: string; servidor: boolean; baixado: boolean; carregado: boolean } | null>(null)
const contexto = ref<string | null>(null)
const lista = ref<HTMLElement | null>(null)
let temporizador: ReturnType<typeof setInterval> | undefined

async function verificarStatus(): Promise<void> {
  try {
    status.value = await statusAssistente()
  } catch {
    status.value = null
  }
}

onMounted(() => {
  verificarStatus()
  temporizador = setInterval(verificarStatus, 5000)
})
onUnmounted(() => clearInterval(temporizador))

function rolar(): void {
  nextTick(() => lista.value?.scrollTo({ top: lista.value.scrollHeight }))
}

async function enviar(texto?: string): Promise<void> {
  const conteudo = (texto ?? pergunta.value).trim()
  if (!conteudo || respondendo.value) return
  pergunta.value = ''
  // historico: as ultimas trocas, para perguntas como "e o que eu faco?"
  const historico = conversa.value.filter((m) => !m.erro).slice(-4).map(({ role, content }) => ({ role, content }))
  conversa.value.push({ role: 'user', content: conteudo })
  const resposta: Mensagem = { role: 'assistant', content: '' }
  conversa.value.push(resposta)
  const indice = conversa.value.length - 1
  respondendo.value = true
  esperandoPrimeiro.value = true
  rolar()
  try {
    await perguntar(conteudo, historico, (pedaco) => {
      esperandoPrimeiro.value = false
      conversa.value[indice] = { ...conversa.value[indice], content: conversa.value[indice].content + pedaco }
      rolar()
    })
  } catch (causa) {
    conversa.value[indice] = { role: 'assistant', content: mensagemDeErro(causa), erro: true }
  } finally {
    respondendo.value = false
    esperandoPrimeiro.value = false
    verificarStatus()
  }
}

async function verContexto(): Promise<void> {
  if (contexto.value) {
    contexto.value = null
    return
  }
  contexto.value = (await api.get<{ contexto: string }>('/api/assistente/contexto')).data.contexto
}
</script>

<template>
  <div class="assistente">
    <div class="gg-cartao chat">
      <header class="cabecalho">
        <div>
          <h2>Assistente da cozinha</h2>
          <p class="sub">
            LLM local ({{ status?.modelo ?? '…' }}) no container <code>ollama</code>, em CPU, sem nuvem e sem chave de API.
          </p>
        </div>
        <span class="status" :data-ok="status?.carregado">
          {{ !status?.servidor ? 'Ollama fora do ar' : !status.baixado ? 'Baixando o modelo…' : !status.carregado ? 'Carregando o modelo…' : 'Modelo pronto' }}
        </span>
      </header>

      <div ref="lista" class="mensagens">
        <div v-if="conversa.length === 0" class="vazio">
          <p>Pergunte sobre o estado atual, os alertas, as previsões da IA, os modelos ou a arquitetura.</p>
          <div class="sugestoes">
            <button v-for="s in SUGESTOES" :key="s" type="button" class="gg-btn gg-btn--mini" @click="enviar(s)">{{ s }}</button>
          </div>
        </div>
        <div v-for="(m, i) in conversa" :key="i" class="mensagem" :data-papel="m.role" :class="{ erro: m.erro }">
          <template v-if="m.role === 'assistant'">
            <p v-if="!m.content && esperandoPrimeiro && i === conversa.length - 1" class="pensando">
              {{ status?.carregado ? 'Pensando…' : 'Carregando o modelo na memória (a primeira resposta demora em CPU)…' }}
            </p>
            <TextoMarkdown v-else :texto="m.content" />
          </template>
          <p v-else>{{ m.content }}</p>
        </div>
      </div>

      <form class="entrada" @submit.prevent="enviar()">
        <input v-model="pergunta" class="gg-input" maxlength="1000" placeholder="Escreva sua pergunta…" :disabled="respondendo" />
        <button type="submit" class="gg-btn gg-btn--primario" :disabled="respondendo || !pergunta.trim()">
          {{ respondendo ? 'Respondendo…' : 'Enviar' }}
        </button>
      </form>
    </div>

    <aside class="gg-cartao lateral">
      <h3>Como o assistente sabe dos dados</h3>
      <p>
        O LLM não acessa banco nenhum e não tem ferramentas. A cada pergunta, o backend monta um resumo com as últimas
        leituras, as previsões da IA, os alertas abertos e as métricas do modelo, e envia junto. Modelos pequenos erram
        ao escolher ferramentas; com o resumo pronto no prompt, eles só precisam ler e explicar.
      </p>
      <p>
        A resposta é texto não confiável: o Markdown é renderizado sem HTML e sem imagens. Há limite de perguntas por
        minuto, e cada pergunta vai para a auditoria.
      </p>
      <button type="button" class="gg-btn gg-btn--mini" @click="verContexto">
        {{ contexto ? 'Esconder o contexto' : 'Ver o contexto enviado ao modelo' }}
      </button>
      <pre v-if="contexto" class="contexto">{{ contexto }}</pre>
    </aside>
  </div>
</template>

<style scoped>
.assistente {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 20rem;
  gap: 1rem;
  height: calc(100vh - 8rem);
  min-height: 520px;
}
.chat {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding-bottom: 1rem;
}
.cabecalho {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  border-bottom: 1px solid var(--gg-line-soft);
  padding-bottom: 0.8rem;
}
.cabecalho h2 {
  margin: 0;
  font-size: 1.05rem;
}
.sub {
  margin: 0.2rem 0 0;
  font-size: 0.82rem;
  color: var(--gg-ink-2);
}
code {
  font-family: var(--gg-mono);
  font-size: 0.88em;
}
.status {
  font-size: 0.78rem;
  font-weight: 600;
  white-space: nowrap;
  color: var(--gg-warn);
}
.status[data-ok='true'] {
  color: var(--gg-ok);
}
.mensagens {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 0.2rem;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.vazio {
  color: var(--gg-ink-2);
}
.sugestoes {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.mensagem {
  max-width: 85%;
  padding: 0.65rem 0.9rem;
  border-radius: 10px;
  line-height: 1.5;
  font-size: 0.93rem;
}
.mensagem p {
  margin: 0;
}
.mensagem[data-papel='user'] {
  align-self: flex-end;
  background: #12201f;
  color: #fff;
}
.mensagem[data-papel='assistant'] {
  align-self: flex-start;
  background: var(--gg-surface-2);
  border: 1px solid var(--gg-line-soft);
}
.mensagem.erro {
  border-color: var(--gg-crit);
  color: var(--gg-crit);
}
.pensando {
  color: var(--gg-ink-2);
  font-style: italic;
  animation: pulsa 1.4s ease-in-out infinite;
}
@keyframes pulsa {
  50% { opacity: 0.5; }
}
.entrada {
  display: flex;
  gap: 0.5rem;
}
.lateral {
  overflow-y: auto;
  font-size: 0.86rem;
  color: var(--gg-ink-2);
}
.lateral h3 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
  color: var(--gg-ink);
}
.contexto {
  margin-top: 0.7rem;
  font-family: var(--gg-mono);
  font-size: 0.7rem;
  white-space: pre-wrap;
  background: var(--gg-surface-2);
  padding: 0.6rem;
  border-radius: 5px;
  max-height: 24rem;
  overflow-y: auto;
}
@media (max-width: 900px) {
  .assistente {
    grid-template-columns: 1fr;
    height: auto;
  }
  .chat {
    height: 70vh;
  }
}
</style>
