<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

import { demonstrarDlq, esvaziarDlq, lerDlq, mensagemDeErro, visaoMensageria } from '../api/client'
import MiniGrafico from '../components/MiniGrafico.vue'
import { dataHora, fmt, fmtMil, hora } from '../lib/formato'
import { useAuth } from '../stores/auth'

interface Consumidor { tag: string; servico: string; usuario: string; origem: string; prefetch: number; ativo: boolean }
interface Fila {
  nome: string; mensagens: number; prontas: number; sem_ack: number; consumidores: number
  consumidor_esperado: string; taxa_entrada: number; taxa_entrega: number; taxa_ack: number
  dlx: string | null; ttl_ms: number | null; max: number | null; lista_consumidores: Consumidor[]
}
interface Visao {
  broker: { versao: string; no: string; mensagens: number; taxa_publicacao: number; taxa_entrega: number; conexoes: number; consumidores: number }
  filas: Fila[]
  exchanges: { nome: string; tipo: string; taxa_entrada: number; taxa_saida: number }[]
  ultimas_mensagens: { rk: string; exchange: string; id: string; instante: string; tipo: string; dispositivo: string | null; conteudo: Record<string, unknown> }[]
}
interface Morta {
  routing_key: string; exchange: string; corpo: string; motivo: string | null; fila_de_origem: string | null
  quantas_vezes: number | null; morreu_em: number | null; topico_mqtt: string | null
}

const auth = useAuth()
const visao = ref<Visao | null>(null)
const dlq = ref<Morta[]>([])
const erro = ref<string | null>(null)
const aviso = ref<string | null>(null)
const profundidade = ref<Record<string, number[]>>({})
let temporizador: ReturnType<typeof setInterval> | undefined
let ciclos = 0

async function atualizar(): Promise<void> {
  try {
    const nova = (await visaoMensageria()) as Visao
    for (const fila of nova.filas) {
      const historico = [...(profundidade.value[fila.nome] ?? []), fila.mensagens].slice(-60)
      profundidade.value = { ...profundidade.value, [fila.nome]: historico }
    }
    visao.value = nova
    if (ciclos++ % 3 === 0) dlq.value = (await lerDlq()) as Morta[]
    erro.value = null
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  }
}

onMounted(() => {
  atualizar()
  temporizador = setInterval(atualizar, 2000)
})
onUnmounted(() => clearInterval(temporizador))

async function demonstrar(): Promise<void> {
  await demonstrarDlq()
  aviso.value = 'Alerta mal formado publicado em gg.eventos. O serviço regras rejeita e o RabbitMQ move para q.dlq.'
  setTimeout(atualizar, 1500)
}

async function esvaziar(): Promise<void> {
  await esvaziarDlq()
  dlq.value = []
  aviso.value = 'DLQ esvaziada.'
}

function resumo(conteudo: Record<string, unknown>): string {
  const texto = JSON.stringify(conteudo)
  return texto.length > 110 ? `${texto.slice(0, 110)}…` : texto
}
</script>

<template>
  <div class="pagina">
    <p class="intro">
      Dois brokers, dois papéis. O <strong>Mosquitto</strong> (MQTT) é a borda: fala com o dispositivo. O
      <strong>RabbitMQ</strong> (AMQP) é o barramento interno: o gateway republica cada leitura na exchange
      <code>gg.telemetria</code> e cada serviço consome a sua fila. Esta página consulta a API de gerenciamento do
      RabbitMQ pelo backend, a cada 2 s; o navegador nunca fala com o broker.
    </p>

    <p v-if="erro" class="gg-alerta gg-alerta--erro">{{ erro }}</p>
    <p v-if="aviso" class="gg-alerta gg-alerta--ok">{{ aviso }}</p>

    <section v-if="visao" class="kpis">
      <div class="gg-cartao kpi"><span>Publicação</span><strong>{{ fmt(visao.broker.taxa_publicacao) }}</strong><small>msg/s</small></div>
      <div class="gg-cartao kpi"><span>Entrega</span><strong>{{ fmt(visao.broker.taxa_entrega) }}</strong><small>msg/s</small></div>
      <div class="gg-cartao kpi"><span>Mensagens nas filas</span><strong>{{ fmtMil(visao.broker.mensagens) }}</strong></div>
      <div class="gg-cartao kpi"><span>Conexões</span><strong>{{ visao.broker.conexoes }}</strong></div>
      <div class="gg-cartao kpi"><span>Consumidores</span><strong>{{ visao.broker.consumidores }}</strong></div>
      <div class="gg-cartao kpi"><span>RabbitMQ</span><strong class="pequeno">{{ visao.broker.versao }}</strong></div>
    </section>

    <section v-if="visao" class="gg-cartao">
      <h2 class="gg-titulo">Filas</h2>
      <div class="gg-rolagem">
        <table class="gg-tabela">
          <thead>
            <tr>
              <th>Fila</th><th>Mensagens</th><th>Últimos 2 min</th><th>Sem ack</th><th>Consumidor</th>
              <th>Entrada</th><th>Entrega</th><th>Regras da fila</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in visao.filas" :key="f.nome" :class="{ parado: f.consumidores === 0 && f.nome !== 'q.dlq', acumulando: f.mensagens > 20 && f.nome !== 'q.dlq' }">
              <td><code>{{ f.nome }}</code></td>
              <td class="gg-num"><strong>{{ fmtMil(f.mensagens) }}</strong></td>
              <td class="mini"><MiniGrafico :valores="profundidade[f.nome] ?? []" :altura="28" :cor="f.mensagens > 20 && f.nome !== 'q.dlq' ? '#c0392b' : '#0b6e75'" /></td>
              <td class="gg-num">{{ f.sem_ack }}</td>
              <td>
                <template v-if="f.lista_consumidores.length">
                  <span v-for="c in f.lista_consumidores" :key="c.tag" class="servico" :title="`${c.usuario} · prefetch ${c.prefetch}`">{{ c.servico }}</span>
                </template>
                <span v-else class="sem-consumidor">{{ f.nome === 'q.dlq' ? 'inspecionada aqui' : `parado (${f.consumidor_esperado})` }}</span>
              </td>
              <td class="gg-num">{{ fmt(f.taxa_entrada) }}/s</td>
              <td class="gg-num">{{ fmt(f.taxa_entrega) }}/s</td>
              <td class="regras">
                <span v-if="f.dlx">DLX {{ f.dlx }}</span>
                <span v-if="f.ttl_ms">TTL {{ f.ttl_ms / 1000 }} s</span>
                <span v-if="f.max">máx {{ fmtMil(f.max) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="nota">
        Para mostrar um consumidor parado: <code>docker compose stop gravador</code>. A fila <code>q.gravador</code>
        cresce (nada se perde: fila durável, mensagens persistentes). Com <code>docker compose start gravador</code>,
        ela esvazia em segundos, gravando em lote no InfluxDB.
      </p>
    </section>

    <div class="duas">
      <section v-if="visao" class="gg-cartao">
        <h2 class="gg-titulo">Exchanges</h2>
        <table class="gg-tabela">
          <thead><tr><th>Exchange</th><th>Tipo</th><th>Entrada</th><th>Saída</th></tr></thead>
          <tbody>
            <tr v-for="e in visao.exchanges" :key="e.nome">
              <td><code>{{ e.nome }}</code></td><td>{{ e.tipo }}</td>
              <td class="gg-num">{{ fmt(e.taxa_entrada) }}/s</td><td class="gg-num">{{ fmt(e.taxa_saida) }}/s</td>
            </tr>
          </tbody>
        </table>
        <p class="nota">
          Routing key <code>telemetry.&lt;zona&gt;.&lt;tipo&gt;.&lt;dispositivo&gt;</code>. A inferência só recebe
          <code>telemetry.*.exaustor.*</code>; o gravador recebe <code>telemetry.#</code> e <code>insight.#</code>.
        </p>
      </section>

      <section class="gg-cartao">
        <div class="titulo-acoes">
          <h2 class="gg-titulo">Fila de mensagens mortas (q.dlq): {{ dlq.length }}</h2>
          <div v-if="auth.pode('administrador')" class="botoes">
            <button type="button" class="gg-btn gg-btn--mini" @click="demonstrar">Publicar mensagem inválida</button>
            <button type="button" class="gg-btn gg-btn--mini gg-btn--perigo" :disabled="!dlq.length" @click="esvaziar">Esvaziar</button>
          </div>
        </div>
        <p v-if="dlq.length === 0" class="gg-vazio">Vazia. Mensagem rejeitada por um consumidor, comando expirado ou payload MQTT inválido cai aqui, preservada.</p>
        <ul v-else class="mortas">
          <li v-for="(m, i) in dlq" :key="i">
            <div><strong>{{ m.motivo }}</strong> · veio de <code>{{ m.fila_de_origem ?? m.exchange }}</code>
              <template v-if="m.topico_mqtt"> (MQTT {{ m.topico_mqtt }})</template>
              · <code>{{ m.routing_key }}</code>
              <template v-if="m.morreu_em"> · {{ dataHora(new Date(m.morreu_em * 1000).toISOString()) }}</template>
            </div>
            <pre>{{ m.corpo }}</pre>
          </li>
        </ul>
      </section>
    </div>

    <section v-if="visao" class="gg-cartao">
      <h2 class="gg-titulo">Últimas mensagens que chegaram à API (fila q.websocket)</h2>
      <div class="gg-rolagem">
        <table class="gg-tabela mensagens">
          <thead><tr><th>Hora</th><th>Exchange</th><th>Routing key</th><th>Tipo</th><th>Conteúdo</th></tr></thead>
          <tbody>
            <tr v-for="m in visao.ultimas_mensagens" :key="m.id">
              <td class="gg-num">{{ hora(m.instante) }}</td>
              <td><code>{{ m.exchange }}</code></td>
              <td><code>{{ m.rk }}</code></td>
              <td>{{ m.tipo }}</td>
              <td class="conteudo">{{ resumo(m.conteudo) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.pagina {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}
.intro {
  margin: 0;
  color: var(--gg-ink-2);
  max-width: 64rem;
}
code {
  font-family: var(--gg-mono);
  font-size: 0.85em;
  background: var(--gg-surface-2);
  padding: 0.05em 0.3em;
  border-radius: 3px;
}
.kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.8rem;
}
.kpi {
  display: flex;
  flex-direction: column;
  padding: 0.8rem 1rem;
}
.kpi span {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--gg-ink-2);
}
.kpi strong {
  font-size: 1.6rem;
  font-variant-numeric: tabular-nums;
}
.kpi strong.pequeno {
  font-size: 1.1rem;
}
.kpi small {
  color: var(--gg-ink-2);
}
.mini {
  width: 9rem;
}
tr.acumulando td {
  background: rgba(192, 57, 43, 0.06);
}
.servico {
  display: inline-block;
  padding: 0.05rem 0.45rem;
  margin-right: 0.25rem;
  border-radius: 4px;
  background: rgba(46, 125, 91, 0.12);
  color: var(--gg-ok);
  font-size: 0.8rem;
  font-weight: 600;
}
.sem-consumidor {
  font-size: 0.8rem;
  color: var(--gg-ink-2);
}
tr.parado .sem-consumidor {
  color: var(--gg-crit);
  font-weight: 600;
}
.regras span {
  display: inline-block;
  margin-right: 0.35rem;
  font-size: 0.75rem;
  color: var(--gg-ink-2);
}
.nota {
  margin: 0.8rem 0 0;
  font-size: 0.84rem;
  color: var(--gg-ink-2);
}
.duas {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
  gap: 1.2rem;
}
.titulo-acoes {
  display: flex;
  justify-content: space-between;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.botoes {
  display: flex;
  gap: 0.4rem;
}
.mortas {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  font-size: 0.84rem;
  max-height: 26rem;
  overflow-y: auto;
}
.mortas li {
  padding: 0.5rem 0.7rem;
  border-radius: 5px;
  background: var(--gg-surface-2);
  border-left: 3px solid var(--gg-crit);
}
.mortas pre {
  margin: 0.35rem 0 0;
  font-family: var(--gg-mono);
  font-size: 0.76rem;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--gg-ink-2);
}
.mensagens td {
  font-size: 0.82rem;
}
.conteudo {
  font-family: var(--gg-mono);
  font-size: 0.76rem !important;
  color: var(--gg-ink-2);
}
</style>
