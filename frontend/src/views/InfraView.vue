<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

import { infraestrutura, mensagemDeErro } from '../api/client'

interface Infra {
  interfaces: { nome: string; url: string; uso: string }[]
  situacao: {
    rabbitmq: boolean
    websocket_clientes: number
    mensagens_recebidas: number
    segundos_sem_telemetria: number | null
    llm: { modelo: string; servidor: boolean; baixado: boolean; carregado: boolean }
  }
}

const dados = ref<Infra | null>(null)
const erro = ref<string | null>(null)
let temporizador: ReturnType<typeof setInterval> | undefined

async function carregar(): Promise<void> {
  try {
    dados.value = (await infraestrutura()) as Infra
    erro.value = null
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  }
}

onMounted(() => {
  carregar()
  temporizador = setInterval(carregar, 5000)
})
onUnmounted(() => clearInterval(temporizador))

const SERVICOS = [
  ['frontend', 'nginx sem root: serve o Vue e repassa /api e /ws para a API. Única porta da aplicação publicada (8080).'],
  ['api', 'FastAPI: REST, WebSocket, login JWT, rotas de IA e do assistente. Consome q.websocket.'],
  ['gateway', 'Ponte MQTT ↔ RabbitMQ, nos dois sentidos. Valida o payload e o cadastro.'],
  ['gravador', 'Consome q.gravador e grava telemetria e previsões no InfluxDB, em lote.'],
  ['regras', 'Regras de negócio (atuador automático) e dono da tabela de alertas.'],
  ['inferencia', 'Aplica os modelos de regressão à telemetria do exaustor; troca de versão sem reiniciar.'],
  ['lab', 'Jobs demorados: geração de dados sintéticos e treino, pelas filas q.jobs.*.'],
  ['simulador', 'O dispositivo: sensores, atuadores e exaustor, publicando e recebendo via MQTT.'],
  ['mosquitto', 'Broker MQTT de borda, sem anônimo e com permissão por tópico.'],
  ['rabbitmq', 'Barramento interno: exchanges topic, filas duráveis, DLQ e um usuário por serviço.'],
  ['postgres', 'Usuários, dispositivos, regras, alertas, jobs, modelos e auditoria.'],
  ['influx', 'Séries temporais: bucket sensores (ao vivo) e lab (amostra sintética).'],
  ['ollama', 'LLM local em CPU (com ollama-init, que baixa o modelo na primeira subida).'],
  ['migrador', 'Roda as migrations do Alembic e o seed, e termina. Os outros esperam por ele.'],
  ['adminer', 'Interface web do PostgreSQL, só em 127.0.0.1.'],
]
</script>

<template>
  <div class="pagina">
    <p v-if="erro" class="gg-alerta gg-alerta--erro">{{ erro }}</p>

    <section class="gg-cartao">
      <h2 class="gg-titulo">Interfaces de administração</h2>
      <p class="nota">
        Abertas só em <code>127.0.0.1</code>: funcionam na máquina da apresentação, não na rede da sala. As credenciais
        estão em <code>secrets/usuarios-demo.txt</code>.
      </p>
      <ul class="links">
        <li v-for="i in dados?.interfaces ?? []" :key="i.url">
          <a :href="i.url" target="_blank" rel="noopener noreferrer">{{ i.nome }}</a>
          <code>{{ i.url }}</code>
          <span>{{ i.uso }}</span>
        </li>
      </ul>
    </section>

    <section v-if="dados" class="gg-cartao">
      <h2 class="gg-titulo">Situação vista pela API</h2>
      <dl class="situacao">
        <div><dt>RabbitMQ</dt><dd>{{ dados.situacao.rabbitmq ? 'conectado' : 'desconectado' }}</dd></div>
        <div><dt>Navegadores no WebSocket</dt><dd>{{ dados.situacao.websocket_clientes }}</dd></div>
        <div><dt>Mensagens recebidas</dt><dd>{{ dados.situacao.mensagens_recebidas }}</dd></div>
        <div><dt>Última telemetria</dt>
          <dd>{{ dados.situacao.segundos_sem_telemetria === null ? 'nunca' : `há ${dados.situacao.segundos_sem_telemetria} s` }}</dd></div>
        <div><dt>LLM ({{ dados.situacao.llm.modelo }})</dt>
          <dd>{{ !dados.situacao.llm.servidor ? 'fora do ar' : !dados.situacao.llm.baixado ? 'baixando' : dados.situacao.llm.carregado ? 'carregado' : 'carregando' }}</dd></div>
      </dl>
    </section>

    <section class="gg-cartao">
      <h2 class="gg-titulo">Containers do docker compose</h2>
      <table class="gg-tabela">
        <tbody>
          <tr v-for="[nome, papel] in SERVICOS" :key="nome">
            <td><code>{{ nome }}</code></td>
            <td>{{ papel }}</td>
          </tr>
        </tbody>
      </table>
      <p class="nota">Ver a saúde de todos: <code>docker compose ps</code>. Logs de um serviço: <code>docker compose logs -f gateway</code>.</p>
    </section>
  </div>
</template>

<style scoped>
.pagina {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}
.nota {
  margin: 0 0 0.8rem;
  font-size: 0.86rem;
  color: var(--gg-ink-2);
}
code {
  font-family: var(--gg-mono);
  font-size: 0.85em;
  background: var(--gg-surface-2);
  padding: 0.05em 0.3em;
  border-radius: 3px;
}
.links {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}
.links li {
  display: grid;
  grid-template-columns: 15rem 15rem 1fr;
  gap: 0.8rem;
  align-items: baseline;
}
.links a {
  font-weight: 600;
  color: #0b6e75;
}
.links span {
  font-size: 0.86rem;
  color: var(--gg-ink-2);
}
.situacao {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.6rem 1rem;
  margin: 0;
}
.situacao dt {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--gg-ink-2);
}
.situacao dd {
  margin: 0;
  font-weight: 600;
}
@media (max-width: 800px) {
  .links li {
    grid-template-columns: 1fr;
    gap: 0.1rem;
  }
}
</style>
