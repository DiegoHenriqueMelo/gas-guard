<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import {
  criarRegra,
  editarConfiguracao,
  editarRegra,
  excluirRegra,
  listarConfiguracoes,
  listarRegras,
  mensagemDeErro,
} from '../api/client'
import type { Configuracao, Regra } from '../api/types'
import { ACOES_POR_TIPO, ROTULO_ACAO, ROTULO_CAMPO } from '../lib/formato'
import { useAuth } from '../stores/auth'
import { useCadastro } from '../stores/cadastro'

const auth = useAuth()
const cadastro = useCadastro()

const regras = ref<Regra[]>([])
const configuracoes = ref<Configuracao[]>([])
const erro = ref<string | null>(null)
const aviso = ref<string | null>(null)
const ehAdmin = computed(() => auth.pode('administrador'))

const nova = reactive({
  nome: '',
  dispositivo_codigo: 'GAS-01',
  campo: 'ppm',
  operador: '>=',
  limite: 1500,
  alvo_codigo: 'SIRENE-01',
  acao: 'ligar',
  ativa: true,
})

const origens = computed(() => cadastro.dispositivos.filter((d) => d.categoria !== 'atuador'))
const alvos = computed(() => cadastro.dispositivos.filter((d) => d.controlavel))
const camposDaOrigem = computed(() => {
  const d = cadastro.porCodigo[nova.dispositivo_codigo]
  if (!d) return []
  return d.tipo === 'exaustor' ? ['vibracao', 'corrente', 'temperatura', 'rpm'] : d.campo_principal ? [d.campo_principal] : []
})
const acoesDoAlvo = computed(() => ACOES_POR_TIPO[cadastro.porCodigo[nova.alvo_codigo]?.tipo ?? ''] ?? [])

async function carregar(): Promise<void> {
  ;[regras.value, configuracoes.value] = await Promise.all([listarRegras(), listarConfiguracoes()])
}
onMounted(carregar)

async function executar(acao: () => Promise<unknown>, texto: string): Promise<void> {
  erro.value = null
  aviso.value = null
  try {
    await acao()
    aviso.value = `${texto} O serviço regras relê a tabela em até 10 s.`
    await carregar()
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  }
}

function criar(): Promise<void> {
  const nome = nova.nome.trim() || `${nova.dispositivo_codigo} ${nova.operador} ${nova.limite} → ${nova.acao} ${nova.alvo_codigo}`
  return executar(() => criarRegra({ ...nova, nome }), 'Regra criada.')
}

function descricao(r: Regra): string {
  return `SE ${r.dispositivo_codigo}.${r.campo} ${r.operador} ${r.limite} ENTÃO ${ROTULO_ACAO[r.acao]?.toLowerCase() ?? r.acao} ${r.alvo_codigo}`
}
</script>

<template>
  <div class="pagina">
    <p class="intro">
      As regras rodam no serviço <code>regras</code>, que consome toda a telemetria da fila <code>q.regras</code>. A
      regra dispara na <strong>transição</strong> (quando a condição passa de falsa para verdadeira) e só manda o
      comando se o atuador ainda não estiver no estado pedido. O comando automático faz o mesmo caminho do botão do
      painel: <code>gg.comandos</code> → gateway → MQTT → simulador, e fica na auditoria como
      <code>comando.regra</code>.
    </p>
    <p v-if="erro" class="gg-alerta gg-alerta--erro">{{ erro }}</p>
    <p v-if="aviso" class="gg-alerta gg-alerta--ok">{{ aviso }}</p>

    <section class="gg-cartao">
      <h2 class="gg-titulo">Regras de negócio</h2>
      <div class="gg-rolagem">
        <table class="gg-tabela">
          <thead><tr><th>#</th><th>Nome</th><th>Regra</th><th>Situação</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in regras" :key="r.id">
              <td class="gg-num">{{ r.id }}</td>
              <td>{{ r.nome }}</td>
              <td><code>{{ descricao(r) }}</code></td>
              <td><span class="gg-selo" :class="r.ativa ? 'gg-selo--ok' : 'gg-selo--off'">{{ r.ativa ? 'ativa' : 'pausada' }}</span></td>
              <td>
                <div v-if="ehAdmin" class="linha-acoes">
                  <button class="gg-btn gg-btn--mini" @click="executar(() => editarRegra(r.id, { ativa: !r.ativa }), r.ativa ? 'Regra pausada.' : 'Regra ativada.')">
                    {{ r.ativa ? 'Pausar' : 'Ativar' }}
                  </button>
                  <button class="gg-btn gg-btn--mini gg-btn--perigo" @click="executar(() => excluirRegra(r.id), 'Regra excluída.')">Excluir</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <form v-if="ehAdmin" class="nova" @submit.prevent="criar">
        <h3>Nova regra</h3>
        <div class="gg-form">
          <label class="gg-campo"><span>Nome</span><input v-model="nova.nome" class="gg-input" maxlength="120" placeholder="opcional" /></label>
          <label class="gg-campo">
            <span>SE o dispositivo</span>
            <select v-model="nova.dispositivo_codigo" class="gg-select" @change="nova.campo = camposDaOrigem[0] ?? ''">
              <option v-for="d in origens" :key="d.codigo" :value="d.codigo">{{ d.codigo }}</option>
            </select>
          </label>
          <label class="gg-campo">
            <span>campo</span>
            <select v-model="nova.campo" class="gg-select">
              <option v-for="c in camposDaOrigem" :key="c" :value="c">{{ ROTULO_CAMPO[c] ?? c }}</option>
            </select>
          </label>
          <label class="gg-campo">
            <span>for</span>
            <select v-model="nova.operador" class="gg-select">
              <option v-for="o in ['>', '>=', '<', '<=']" :key="o" :value="o">{{ o }}</option>
            </select>
          </label>
          <label class="gg-campo"><span>limite</span><input v-model.number="nova.limite" class="gg-input" type="number" step="any" /></label>
          <label class="gg-campo">
            <span>ENTÃO no atuador</span>
            <select v-model="nova.alvo_codigo" class="gg-select" @change="nova.acao = acoesDoAlvo[0] ?? ''">
              <option v-for="d in alvos" :key="d.codigo" :value="d.codigo">{{ d.codigo }}</option>
            </select>
          </label>
          <label class="gg-campo">
            <span>fazer</span>
            <select v-model="nova.acao" class="gg-select">
              <option v-for="a in acoesDoAlvo" :key="a" :value="a">{{ ROTULO_ACAO[a] }}</option>
            </select>
          </label>
        </div>
        <div class="gg-acoes"><button type="submit" class="gg-btn gg-btn--primario">Criar regra</button></div>
      </form>
    </section>

    <section class="gg-cartao">
      <h2 class="gg-titulo">Limites dos alertas da IA</h2>
      <p class="nota">
        Lidos pelo serviço <code>inferencia</code> a cada 15 s (sem reiniciar). A histerese evita alerta piscando: abre
        depois de N previsões seguidas ruins e fecha depois de M seguidas boas.
      </p>
      <table class="gg-tabela">
        <thead><tr><th>Chave</th><th>Descrição</th><th>Valor</th></tr></thead>
        <tbody>
          <tr v-for="c in configuracoes" :key="c.chave">
            <td><code>{{ c.chave }}</code></td>
            <td>{{ c.descricao }}</td>
            <td>
              <input v-if="ehAdmin" class="gg-input valor" type="number" step="any" :value="c.valor"
                     @change="executar(() => editarConfiguracao(c.chave, Number(($event.target as HTMLInputElement).value)), 'Limite salvo.')" />
              <strong v-else>{{ c.valor }}</strong>
            </td>
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
  gap: 1.2rem;
}
.intro,
.nota {
  margin: 0;
  color: var(--gg-ink-2);
  max-width: 64rem;
}
.nota {
  margin-bottom: 0.8rem;
  font-size: 0.86rem;
}
code {
  font-family: var(--gg-mono);
  font-size: 0.85em;
  background: var(--gg-surface-2);
  padding: 0.05em 0.3em;
  border-radius: 3px;
}
.nova {
  margin-top: 1.2rem;
  border-top: 1px solid var(--gg-line-soft);
  padding-top: 1rem;
}
.nova h3 {
  margin: 0 0 0.6rem;
  font-size: 0.9rem;
}
.linha-acoes {
  display: flex;
  gap: 0.4rem;
  justify-content: flex-end;
}
.valor {
  width: 7rem;
}
</style>
