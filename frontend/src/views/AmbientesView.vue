<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  criarAmbiente,
  editarAmbiente,
  excluirAmbiente,
  listarAmbientes,
  mensagemDeErro,
} from '../api/client'
import type { Ambiente } from '../api/types'
import ModalConfirmacao from '../components/ModalConfirmacao.vue'

const ambientes = ref<Ambiente[]>([])
const carregando = ref(true)
const salvando = ref(false)

const erro = ref<string | null>(null)
const aviso = ref<string | null>(null)

// Ambiente aguardando confirmacao de exclusao. null = modal fechado.
const paraExcluir = ref<Ambiente | null>(null)

// null = o formulario esta em modo de criacao.
const editandoId = ref<number | null>(null)
const nome = ref('')
const descricao = ref('')

function limparFormulario(): void {
  editandoId.value = null
  nome.value = ''
  descricao.value = ''
}

function prepararEdicao(ambiente: Ambiente): void {
  editandoId.value = ambiente.id
  nome.value = ambiente.nome
  descricao.value = ambiente.descricao ?? ''
  erro.value = null
  aviso.value = null
}

async function carregar(): Promise<void> {
  carregando.value = true
  try {
    ambientes.value = await listarAmbientes()
    erro.value = null
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  } finally {
    carregando.value = false
  }
}

async function salvar(): Promise<void> {
  salvando.value = true
  erro.value = null
  aviso.value = null

  // string vazia vira null: a coluna e opcional no banco, e mandar ""
  // gravaria uma descricao em branco em vez de "sem descricao".
  const descricaoLimpa = descricao.value.trim() || null

  try {
    if (editandoId.value === null) {
      const novo = await criarAmbiente({
        nome: nome.value.trim(),
        descricao: descricaoLimpa,
      })
      aviso.value = `Ambiente "${novo.nome}" criado.`
    } else {
      const alterado = await editarAmbiente(editandoId.value, {
        nome: nome.value.trim(),
        descricao: descricaoLimpa,
      })
      aviso.value = `Ambiente "${alterado.nome}" atualizado.`
    }

    limparFormulario()
    await carregar()
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  } finally {
    salvando.value = false
  }
}

async function confirmarExclusao(): Promise<void> {
  const ambiente = paraExcluir.value
  paraExcluir.value = null

  if (ambiente === null) return

  erro.value = null
  aviso.value = null

  try {
    await excluirAmbiente(ambiente.id)
    aviso.value = `Ambiente "${ambiente.nome}" excluído.`

    // se estava sendo editado, o formulario apontaria para um id que
    // nao existe mais
    if (editandoId.value === ambiente.id) limparFormulario()

    await carregar()
  } catch (causa) {
    // o backend devolve 409 quando o ambiente ainda tem dispositivos
    erro.value = mensagemDeErro(causa)
  }
}

function formatarData(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR')
}

onMounted(carregar)
</script>

<template>
  <div class="pagina">
    <section class="gg-cartao">
      <h2 class="gg-titulo">
        {{ editandoId === null ? 'Novo ambiente' : `Editando ambiente #${editandoId}` }}
      </h2>

      <p v-if="erro" class="gg-alerta gg-alerta--erro">{{ erro }}</p>
      <p v-else-if="aviso" class="gg-alerta gg-alerta--ok">{{ aviso }}</p>

      <form @submit.prevent="salvar">
        <div class="gg-form">
          <label class="gg-campo">
            <span>Nome</span>
            <input
              v-model="nome"
              class="gg-input"
              required
              maxlength="100"
              placeholder="Cozinha industrial"
            />
          </label>

          <label class="gg-campo">
            <span>Descrição</span>
            <input
              v-model="descricao"
              class="gg-input"
              maxlength="255"
              placeholder="opcional"
            />
          </label>
        </div>

        <div class="gg-acoes">
          <button
            type="submit"
            class="gg-btn gg-btn--primario"
            :disabled="salvando || nome.trim() === ''"
          >
            {{ editandoId === null ? 'Criar' : 'Salvar' }}
          </button>

          <button
            v-if="editandoId !== null"
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
      <h2 class="gg-titulo">Ambientes cadastrados</h2>

      <p v-if="carregando" class="gg-vazio">Carregando…</p>
      <p v-else-if="ambientes.length === 0" class="gg-vazio">
        Nenhum ambiente cadastrado ainda.
      </p>

      <div v-else class="gg-rolagem">
        <table class="gg-tabela">
          <thead>
            <tr>
              <th>#</th>
              <th>Nome</th>
              <th>Descrição</th>
              <th>Criado em</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="ambiente in ambientes" :key="ambiente.id">
              <td class="gg-num">{{ ambiente.id }}</td>
              <td>{{ ambiente.nome }}</td>
              <td>{{ ambiente.descricao ?? '—' }}</td>
              <td class="gg-num">{{ formatarData(ambiente.criado_em) }}</td>
              <td>
                <div class="linha-acoes">
                  <button
                    class="gg-btn gg-btn--mini"
                    @click="prepararEdicao(ambiente)"
                  >
                    Editar
                  </button>
                  <button
                    class="gg-btn gg-btn--mini gg-btn--perigo"
                    @click="paraExcluir = ambiente"
                  >
                    Excluir
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <ModalConfirmacao
      :aberto="paraExcluir !== null"
      titulo="Excluir ambiente"
      :mensagem="`O ambiente &quot;${paraExcluir?.nome}&quot; será removido permanentemente. Ambientes com dispositivos vinculados não podem ser excluídos.`"
      rotulo-confirmar="Excluir"
      perigo
      @confirmar="confirmarExclusao"
      @cancelar="paraExcluir = null"
    />
  </div>
</template>

<style scoped>
.pagina {
  display: flex;
  flex-direction: column;
  gap: 1.4rem;
}

.linha-acoes {
  display: flex;
  gap: 0.4rem;
  justify-content: flex-end;
}
</style>
