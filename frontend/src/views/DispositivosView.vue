<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  criarDispositivo,
  desativarDispositivo,
  editarDispositivo,
  mensagemDeErro,
} from '../api/client'
import type { Dispositivo } from '../api/types'
import ModalConfirmacao from '../components/ModalConfirmacao.vue'
import { haQuanto } from '../lib/formato'
import { useAuth } from '../stores/auth'
import { useCadastro } from '../stores/cadastro'

const auth = useAuth()
const cadastro = useCadastro()

const TIPOS = [
  { valor: 'gas', texto: 'Sensor de gás (ppm)' },
  { valor: 'temperatura', texto: 'Sensor de temperatura (°C)' },
  { valor: 'umidade', texto: 'Sensor de umidade (%)' },
  { valor: 'luminosidade', texto: 'Sensor de luminosidade (lx)' },
  { valor: 'vazao', texto: 'Medidor de vazão (m³/h)' },
  { valor: 'valvula', texto: 'Válvula solenoide (atuador)' },
  { valor: 'sirene', texto: 'Sirene (atuador)' },
  { valor: 'exaustor', texto: 'Exaustor (equipamento + atuador)' },
]

const salvando = ref(false)
const erro = ref<string | null>(null)
const aviso = ref<string | null>(null)
const paraDesativar = ref<Dispositivo | null>(null)

// null = modo de criacao. Guardamos o CODIGO: as rotas sao por codigo.
const editandoCodigo = ref<string | null>(null)
const codigo = ref('')
const nome = ref('')
const tipo = ref('gas')
const ambienteId = ref<number | null>(null)
const ativo = ref(true)
const faixa = ref<{ normal_min: number | null; normal_max: number | null; critico_min: number | null; critico_max: number | null }>({
  normal_min: null, normal_max: null, critico_min: null, critico_max: null,
})

const semAmbientes = computed(() => cadastro.ambientes.length === 0)
const ehAdmin = computed(() => auth.pode('administrador'))

function nomeDoAmbiente(id: number): string {
  return cadastro.ambientes.find((a) => a.id === id)?.nome ?? `#${id}`
}

function textoFaixa(d: Dispositivo): string {
  if (d.normal_max === null && d.critico_max === null && d.normal_min === null && d.critico_min === null) return '—'
  const partes = []
  if (d.normal_min !== null || d.normal_max !== null) partes.push(`normal ${d.normal_min ?? '−∞'} a ${d.normal_max ?? '∞'}`)
  if (d.critico_min !== null || d.critico_max !== null) partes.push(`crítico fora de ${d.critico_min ?? '−∞'} a ${d.critico_max ?? '∞'}`)
  return `${partes.join(' · ')} ${d.unidade ?? ''}`
}

function limparFormulario(): void {
  editandoCodigo.value = null
  codigo.value = ''
  nome.value = ''
  tipo.value = 'gas'
  ambienteId.value = cadastro.ambientes[0]?.id ?? null
  ativo.value = true
  faixa.value = { normal_min: null, normal_max: null, critico_min: null, critico_max: null }
}

function prepararEdicao(d: Dispositivo): void {
  editandoCodigo.value = d.codigo
  codigo.value = d.codigo
  nome.value = d.nome
  tipo.value = d.tipo
  ambienteId.value = d.ambiente_id
  ativo.value = d.ativo
  faixa.value = { normal_min: d.normal_min, normal_max: d.normal_max, critico_min: d.critico_min, critico_max: d.critico_max }
  erro.value = null
  aviso.value = null
}

function numeroOuNulo(valor: number | string | null): number | null {
  return valor === '' || valor === null || Number.isNaN(Number(valor)) ? null : Number(valor)
}

async function salvar(): Promise<void> {
  if (ambienteId.value === null) return
  salvando.value = true
  erro.value = null
  aviso.value = null
  const limites = {
    normal_min: numeroOuNulo(faixa.value.normal_min),
    normal_max: numeroOuNulo(faixa.value.normal_max),
    critico_min: numeroOuNulo(faixa.value.critico_min),
    critico_max: numeroOuNulo(faixa.value.critico_max),
  }
  try {
    if (editandoCodigo.value === null) {
      const novo = await criarDispositivo({
        codigo: codigo.value.trim(), nome: nome.value.trim(), ambiente_id: ambienteId.value, tipo: tipo.value, ...limites,
      })
      aviso.value = `Dispositivo "${novo.codigo}" cadastrado. O gateway passa a aceitar as leituras dele em até 15 s.`
    } else {
      // O codigo nao muda: e a chave que liga o dispositivo ao topico MQTT,
      // a routing key e as series ja gravadas no InfluxDB.
      const alterado = await editarDispositivo(editandoCodigo.value, {
        nome: nome.value.trim(), ambiente_id: ambienteId.value, ativo: ativo.value, ...limites,
      })
      aviso.value = `Dispositivo "${alterado.codigo}" atualizado.`
    }
    limparFormulario()
    await cadastro.carregar()
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  } finally {
    salvando.value = false
  }
}

async function confirmarDesativacao(): Promise<void> {
  const d = paraDesativar.value
  paraDesativar.value = null
  if (!d) return
  try {
    await desativarDispositivo(d.codigo)
    aviso.value = `Dispositivo "${d.codigo}" desativado.`
    await cadastro.carregar()
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  }
}

async function reativar(d: Dispositivo): Promise<void> {
  try {
    await editarDispositivo(d.codigo, { ativo: true })
    aviso.value = `Dispositivo "${d.codigo}" reativado.`
    await cadastro.carregar()
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  }
}

onMounted(async () => {
  await cadastro.carregar()
  limparFormulario()
})
</script>

<template>
  <div class="pagina">
    <section v-if="ehAdmin" class="gg-cartao">
      <h2 class="gg-titulo">{{ editandoCodigo === null ? 'Novo dispositivo' : `Editando ${editandoCodigo}` }}</h2>
      <p v-if="erro" class="gg-alerta gg-alerta--erro">{{ erro }}</p>
      <p v-else-if="aviso" class="gg-alerta gg-alerta--ok">{{ aviso }}</p>
      <p v-if="semAmbientes" class="gg-alerta gg-alerta--erro">Cadastre um ambiente antes: todo dispositivo pertence a um.</p>

      <form @submit.prevent="salvar">
        <div class="gg-form">
          <label class="gg-campo">
            <span>Código</span>
            <input v-model="codigo" class="gg-input" required maxlength="50" pattern="[A-Za-z0-9_\-]{2,50}"
                   placeholder="GAS-02" :disabled="editandoCodigo !== null" />
          </label>
          <label class="gg-campo">
            <span>Nome</span>
            <input v-model="nome" class="gg-input" required maxlength="100" placeholder="Detector da despensa" />
          </label>
          <label class="gg-campo">
            <span>Tipo</span>
            <select v-model="tipo" class="gg-select" :disabled="editandoCodigo !== null">
              <option v-for="t in TIPOS" :key="t.valor" :value="t.valor">{{ t.texto }}</option>
            </select>
          </label>
          <label class="gg-campo">
            <span>Ambiente</span>
            <select v-model.number="ambienteId" class="gg-select" required>
              <option v-for="a in cadastro.ambientes" :key="a.id" :value="a.id">{{ a.nome }} ({{ a.zona }})</option>
            </select>
          </label>
          <label v-if="editandoCodigo !== null" class="gg-campo">
            <span>Situação</span>
            <span class="gg-checkbox"><input v-model="ativo" type="checkbox" /> Ativo</span>
          </label>
        </div>

        <fieldset class="faixa">
          <legend>Faixa do sensor (vazio = sem limite daquele lado)</legend>
          <div class="gg-form">
            <label class="gg-campo"><span>Normal a partir de</span><input v-model="faixa.normal_min" class="gg-input" type="number" step="any" /></label>
            <label class="gg-campo"><span>Normal abaixo de</span><input v-model="faixa.normal_max" class="gg-input" type="number" step="any" /></label>
            <label class="gg-campo"><span>Crítico abaixo de</span><input v-model="faixa.critico_min" class="gg-input" type="number" step="any" /></label>
            <label class="gg-campo"><span>Crítico a partir de</span><input v-model="faixa.critico_max" class="gg-input" type="number" step="any" /></label>
          </div>
          <p class="nota">Dentro da faixa normal: verde. Fora dela, mas dentro da crítica: atenção. Fora das duas: crítico (e alerta).</p>
        </fieldset>

        <div class="gg-acoes">
          <button type="submit" class="gg-btn gg-btn--primario" :disabled="salvando || semAmbientes || !codigo.trim() || !nome.trim()">
            {{ editandoCodigo === null ? 'Cadastrar' : 'Salvar' }}
          </button>
          <button v-if="editandoCodigo !== null" type="button" class="gg-btn" @click="limparFormulario">Cancelar</button>
        </div>
      </form>
    </section>
    <p v-else class="gg-alerta gg-alerta--ok">Cadastro e edição de dispositivos são feitos pelo administrador.</p>

    <section class="gg-cartao">
      <h2 class="gg-titulo">Dispositivos cadastrados</h2>
      <p v-if="!cadastro.carregado" class="gg-vazio">Carregando…</p>
      <div v-else class="gg-rolagem">
        <table class="gg-tabela">
          <thead>
            <tr><th>Código</th><th>Nome</th><th>Categoria</th><th>Ambiente</th><th>Faixa</th><th>Situação</th><th>Último contato</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="d in cadastro.dispositivos" :key="d.id">
              <td><code>{{ d.codigo }}</code></td>
              <td>{{ d.nome }}</td>
              <td>{{ d.categoria }} · {{ d.tipo }}</td>
              <td>{{ nomeDoAmbiente(d.ambiente_id) }}</td>
              <td class="faixa-texto">{{ textoFaixa(d) }}</td>
              <td><span class="gg-selo" :class="d.ativo ? 'gg-selo--ok' : 'gg-selo--off'">{{ d.ativo ? 'Ativo' : 'Inativo' }}</span></td>
              <td class="gg-num">{{ haQuanto(d.ultimo_contato) }}</td>
              <td>
                <div v-if="ehAdmin" class="linha-acoes">
                  <button class="gg-btn gg-btn--mini" @click="prepararEdicao(d)">Editar</button>
                  <button v-if="d.ativo" class="gg-btn gg-btn--mini gg-btn--perigo" @click="paraDesativar = d">Desativar</button>
                  <button v-else class="gg-btn gg-btn--mini" @click="reativar(d)">Reativar</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="nota">
        A posição de cada dispositivo na cena 3D fica no frontend, indexada por este mesmo código. Um dispositivo novo,
        sem posição definida, aparece na prateleira à direita da cozinha.
      </p>
    </section>

    <ModalConfirmacao
      :aberto="paraDesativar !== null"
      titulo="Desativar dispositivo"
      :mensagem="`O dispositivo &quot;${paraDesativar?.codigo}&quot; deixa de ser aceito pelo gateway e some do painel e da cena. O histórico no InfluxDB é preservado e ele pode ser reativado.`"
      rotulo-confirmar="Desativar"
      perigo
      @confirmar="confirmarDesativacao"
      @cancelar="paraDesativar = null"
    />
  </div>
</template>

<style scoped>
.pagina {
  display: flex;
  flex-direction: column;
  gap: 1.4rem;
}
.faixa {
  border: 1px solid var(--gg-line-soft);
  border-radius: 6px;
  margin: 1rem 0 0;
  padding: 0.6rem 1rem 0.8rem;
}
legend {
  font-size: 0.78rem;
  font-weight: 600;
  padding: 0 0.3rem;
}
.nota {
  margin: 0.6rem 0 0;
  font-size: 0.82rem;
  color: var(--gg-ink-2);
}
.faixa-texto {
  font-size: 0.8rem;
  color: var(--gg-ink-2);
}
code {
  font-family: var(--gg-mono);
  font-size: 0.88em;
}
.linha-acoes {
  display: flex;
  gap: 0.4rem;
  justify-content: flex-end;
}
</style>
