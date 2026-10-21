<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { mensagemDeErro } from '../api/client'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()
const rota = useRoute()

const usuario = ref('')
const senha = ref('')
const erro = ref<string | null>(null)
const entrando = ref(false)

async function entrar(): Promise<void> {
  entrando.value = true
  erro.value = null
  try {
    await auth.login(usuario.value.trim(), senha.value)
    const volta = typeof rota.query.volta === 'string' ? rota.query.volta : '/'
    router.replace(volta)
  } catch (causa) {
    erro.value = mensagemDeErro(causa)
  } finally {
    entrando.value = false
  }
}
</script>

<template>
  <div class="fundo">
    <form class="cartao" @submit.prevent="entrar">
      <div class="marca">
        <span aria-hidden="true">🧯</span>
        <div>
          <h1>Gas-Guard</h1>
          <p>Vazamento de gás e manutenção preditiva do exaustor</p>
        </div>
      </div>

      <p v-if="erro" class="gg-alerta gg-alerta--erro">{{ erro }}</p>

      <label class="gg-campo">
        <span>Usuário</span>
        <input v-model="usuario" class="gg-input" autocomplete="username" required autofocus />
      </label>
      <label class="gg-campo">
        <span>Senha</span>
        <input v-model="senha" class="gg-input" type="password" autocomplete="current-password" required />
      </label>

      <button class="gg-btn gg-btn--primario" type="submit" :disabled="entrando || !usuario || !senha">
        {{ entrando ? 'Entrando…' : 'Entrar' }}
      </button>

      <p class="dica">
        Usuários de demonstração: <code>administrador</code>, <code>operador</code> e
        <code>visualizador</code>. As senhas estão em <code>secrets/usuarios-demo.txt</code>,
        gerado por <code>scripts/gerar_segredos.py</code>.
      </p>
    </form>
  </div>
</template>

<style scoped>
.fundo {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: radial-gradient(circle at 20% 10%, #1f3a37, #0f1d1c 60%);
}
.cartao {
  width: min(24rem, 100%);
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: var(--gg-surface);
  border-radius: 10px;
  padding: 1.8rem 1.7rem;
  box-shadow: 0 24px 60px -24px rgba(0, 0, 0, 0.6);
}
.marca {
  display: flex;
  gap: 0.8rem;
  align-items: center;
  margin-bottom: 0.4rem;
}
.marca span {
  font-size: 2rem;
}
h1 {
  margin: 0;
  font-size: 1.4rem;
}
.marca p {
  margin: 0.1rem 0 0;
  color: var(--gg-ink-2);
  font-size: 0.85rem;
}
.dica {
  margin: 0;
  font-size: 0.78rem;
  color: var(--gg-ink-2);
  line-height: 1.5;
}
code {
  font-family: var(--gg-mono);
  font-size: 0.92em;
  background: var(--gg-surface-2);
  padding: 0.05em 0.3em;
  border-radius: 3px;
}
</style>
