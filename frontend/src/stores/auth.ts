import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { entrar, gravarSessao, lerSessao } from '../api/client'
import type { Papel, UsuarioToken } from '../api/types'

// Do menor para o maior poder, igual ao backend (app/auth/models.py).
const NIVEL: Record<Papel, number> = { visualizador: 0, operador: 1, administrador: 2 }

export const useAuth = defineStore('auth', () => {
  const sessao = ref(lerSessao())

  const usuario = computed<UsuarioToken | null>(() => sessao.value?.usuario ?? null)
  const logado = computed(() => sessao.value !== null)

  /** O botao some para quem nao pode. Quem decide de verdade e o backend. */
  function pode(papel: Papel): boolean {
    const atual = usuario.value?.papel
    return atual !== undefined && NIVEL[atual] >= NIVEL[papel]
  }

  async function login(nome: string, senha: string): Promise<void> {
    const resposta = await entrar(nome, senha)
    sessao.value = resposta
    gravarSessao(resposta)
  }

  function logout(): void {
    sessao.value = null
    gravarSessao(null)
  }

  return { usuario, logado, pode, login, logout }
})
