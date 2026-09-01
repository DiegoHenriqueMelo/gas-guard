<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  criarDispositivo,
  desativarDispositivo,
  editarDispositivo,
  listarAmbientes,
  listarDispositivos,
  mensagemDeErro,
} from '../api/client'
import type { Ambiente, Dispositivo } from '../api/types'
import ModalConfirmacao from '../components/ModalConfirmacao.vue'

const dispositivos = ref<Dispositivo[]>([])
const ambientes = ref<Ambiente[]>([])
const carregando = ref(true)
const salvando = ref(false)

const erro = ref<string | null>(null)
const aviso = ref<string | null>(null)

// Dispositivo aguardando confirmacao de desativacao. null = modal fechado.
const paraDesativar = ref<Dispositivo | null>(null)

// null = modo de criacao. Guardamos o CODIGO, nao o id, porque as rotas
// de dispositivo do backend sao indexadas por codigo.
const editandoCodigo = ref<string | null>(null)
const codigo = ref('')
const nome = ref('')
const ambienteId = ref<number | null>(null)
const ativo = ref(true)

const semAmbientes = computed(() => ambientes.value.length === 0)

function nomeDoAmbiente(id: number): string {
  return ambientes.value.find((a) => a.id === id)?.nome ?? `#${id}`
}

function limparFormulario(): void {
  editandoCodigo.value = null
  codigo.value = ''
  nome.value = ''
  ambienteId.value = ambientes.value[0]?.id ?? null
  ativo.value = true
}

function prepararEdicao(dispositivo: Dispositivo): void {
  editandoCodigo.value = dispositivo.codigo
  codigo.value = dispositivo.codigo
  nome.value = dispositivo.nome
  ambienteId.value = dispositivo.ambiente_id
  ativo.value = dispositivo.ativo
  erro.value = null
  aviso.value = null
}

async function carregar(): Promise<void> {
  carregando.value = true
  try {
    const [listaAmbientes, listaDispositivos] = await Promise.all([
      listarAmbientes(),
      listarDispositivos(),
    ])

    ambientes.value = listaAmbientes
    dispositivos.value = listaDispositivos

    if (ambienteId.value === null) {
      ambienteId.value = listaAmbientes[0]?.id ?? null
    }

    erro.value = null
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  } finally {
    carregando.value = false
  }
}

async function salvar(): Promise<void> {
  if (ambienteId.value === null) return

  salvando.value = true
  erro.value = null
  aviso.value = null

  try {
    if (editandoCodigo.value === null) {
      const novo = await criarDispositivo({
        codigo: codigo.value.trim(),
        nome: nome.value.trim(),
        ambiente_id: ambienteId.value,
      })
      aviso.value = `Dispositivo "${novo.codigo}" cadastrado.`
    } else {
      // O PATCH do backend nao aceita "codigo": trocar o identificador
      // quebraria o vinculo com as series ja gravadas no InfluxDB.
      const alterado = await editarDispositivo(editandoCodigo.value, {
        nome: nome.value.trim(),
        ambiente_id: ambienteId.value,
        ativo: ativo.value,
      })
      aviso.value = `Dispositivo "${alterado.codigo}" atualizado.`
    }

    limparFormulario()
    await carregar()
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  } finally {
    salvando.value = false
  }
}

async function confirmarDesativacao(): Promise<void> {
  const dispositivo = paraDesativar.value
  paraDesativar.value = null

  if (dispositivo === null) return

  erro.value = null
  aviso.value = null

  try {
    await desativarDispositivo(dispositivo.codigo)
    aviso.value = `Dispositivo "${dispositivo.codigo}" desativado.`
    await carregar()
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  }
}

async function reativar(dispositivo: Dispositivo): Promise<void> {
  erro.value = null
  aviso.value = null

  try {
    await editarDispositivo(dispositivo.codigo, { ativo: true })
    aviso.value = `Dispositivo "${dispositivo.codigo}" reativado.`
    await carregar()
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  }
}

function formatarContato(iso: string | null): string {
  if (!iso) return 'nunca'
  return new Date(iso).toLocaleString('pt-BR')
}

onMounted(carregar)
</script>

<template>
  <div class="pagina">
    <section class="gg-cartao">
      <h2 class="gg-titulo">
        {{
          editandoCodigo === null
            ? 'Novo dispositivo'
            : `Editando ${editandoCodigo}`
        }}
      </h2>

      <p v-if="erro" class="gg-alerta gg-alerta--erro">{{ erro }}</p>
      <p v-else-if="aviso" class="gg-alerta gg-alerta--ok">{{ aviso }}</p>

      <p v-if="semAmbientes && !carregando" class="gg-alerta gg-alerta--erro">
        Cadastre um ambiente antes: todo dispositivo precisa pertencer a um.
      </p>

      <form @submit.prevent="salvar">
        <div class="gg-form">
          <label class="gg-campo">
            <span>Código</span>
            <input
              v-model="codigo"
              class="gg-input"
              required
              maxlength="50"
              placeholder="ESP32-COZINHA-01"
              :disabled="editandoCodigo !== null"
            />
          </label>

          <label class="gg-campo">
            <span>Nome</span>
            <input
              v-model="nome"
              class="gg-input"
              required
              maxlength="100"
              placeholder="Sensor da cozinha"
            />
          </label>

          <label class="gg-campo">
            <span>Ambiente</span>
            <select v-model.number="ambienteId" class="gg-select" required>
              <option v-for="item in ambientes" :key="item.id" :value="item.id">
                {{ item.nome }}
              </option>
            </select>
          </label>

          <label v-if="editandoCodigo !== null" class="gg-campo">
            <span>Situação</span>
            <span class="gg-checkbox">
              <input v-model="ativo" type="checkbox" />
              Ativo
            </span>
          </label>
        </div>

        <p v-if="editandoCodigo !== null" class="nota">
          O código não pode ser alterado: ele é a chave que liga o dispositivo
          às séries já gravadas no InfluxDB.
        </p>

        <div class="gg-acoes">
          <button
            type="submit"
            class="gg-btn gg-btn--primario"
            :disabled="
              salvando ||
              semAmbientes ||
              codigo.trim() === '' ||
              nome.trim() === ''
            "
          >
            {{ editandoCodigo === null ? 'Cadastrar' : 'Salvar' }}
          </button>

          <button
            v-if="editandoCodigo !== null"
            type="button"
            class="gg-btn"
            @click="limparFormulario"
          >
            Cancelar
          </button>
        </div>
      </form>
    </section>

    <section class="gg-cartao">
      <h2 class="gg-titulo">Dispositivos cadastrados</h2>

      <p v-if="carregando" class="gg-vazio">Carregando…</p>
      <p v-else-if="dispositivos.length === 0" class="gg-vazio">
        Nenhum dispositivo cadastrado ainda.
      </p>

      <div v-else class="gg-rolagem">
        <table class="gg-tabela">
          <thead>
            <tr>
              <th>Código</th>
              <th>Nome</th>
              <th>Ambiente</th>
              <th>Situação</th>
              <th>Último contato</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in dispositivos" :key="item.id">
              <td>{{ item.codigo }}</td>
              <td>{{ item.nome }}</td>
              <td>{{ nomeDoAmbiente(item.ambiente_id) }}</td>
              <td>
                <span
                  class="gg-selo"
                  :class="item.ativo ? 'gg-selo--ok' : 'gg-selo--off'"
                >
                  {{ item.ativo ? 'Ativo' : 'Inativo' }}
                </span>
              </td>
              <td class="gg-num">{{ formatarContato(item.ultimo_contato) }}</td>
              <td>
                <div class="linha-acoes">
                  <button
                    class="gg-btn gg-btn--mini"
                    @click="prepararEdicao(item)"
                  >
                    Editar
                  </button>
                  <button
                    v-if="item.ativo"
                    class="gg-btn gg-btn--mini gg-btn--perigo"
                    @click="paraDesativar = item"
                  >
                    Desativar
                  </button>
                  <button
                    v-else
                    class="gg-btn gg-btn--mini"
                    @click="reativar(item)"
                  >
                    Reativar
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <ModalConfirmacao
      :aberto="paraDesativar !== null"
      titulo="Desativar dispositivo"
      :mensagem="`O dispositivo &quot;${paraDesativar?.codigo}&quot; deixará de aparecer como ativo. O histórico dele no InfluxDB é preservado e ele pode ser reativado depois.`"
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

.nota {
  margin: 0.9rem 0 0;
  font-size: 0.85rem;
  color: var(--gg-ink-2);
}

.linha-acoes {
  display: flex;
  gap: 0.4rem;
  justify-content: flex-end;
}
</style>
