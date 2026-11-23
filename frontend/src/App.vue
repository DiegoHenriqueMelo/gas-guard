<script setup lang="ts">
import { computed, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import type { Papel } from './api/types'
import { useAuth } from './stores/auth'
import { useCadastro } from './stores/cadastro'
import { useTempoReal } from './stores/tempoReal'

const auth = useAuth()
const tempoReal = useTempoReal()
const cadastro = useCadastro()
const rota = useRoute()
const router = useRouter()

interface Link {
  para: string
  texto: string
  papel?: Papel
}

const MENU: { secao: string; links: Link[] }[] = [
  {
    secao: 'Monitoramento',
    links: [
      { para: '/', texto: 'Painel' },
      { para: '/gemeo', texto: 'Gêmeo 3D' },
      { para: '/insights', texto: 'Insights' },
    ],
  },
  {
    secao: 'Inteligência artificial',
    links: [
      { para: '/laboratorio', texto: 'Laboratório' },
      { para: '/treinamento', texto: 'Treinamento' },
      { para: '/assistente', texto: 'Assistente' },
    ],
  },
  {
    secao: 'Sistema',
    links: [
      { para: '/mensageria', texto: 'Mensageria' },
      { para: '/dispositivos', texto: 'Dispositivos' },
      { para: '/ambientes', texto: 'Ambientes' },
      { para: '/regras', texto: 'Regras e limites' },
      { para: '/auditoria', texto: 'Auditoria', papel: 'administrador' },
      { para: '/infraestrutura', texto: 'Infraestrutura' },
    ],
  },
]

const ROTULO_PAPEL: Record<Papel, string> = {
  visualizador: 'Visualizador',
  operador: 'Operador',
  administrador: 'Administrador',
}

const naTelaDeLogin = computed(() => rota.name === 'login')

// a conexao em tempo real vive enquanto houver sessao, em qualquer pagina
watch(
  () => auth.logado,
  (logado) => {
    if (logado) {
      tempoReal.conectar()
      cadastro.carregar().catch(() => {})
    } else {
      tempoReal.desconectar()
    }
  },
  { immediate: true },
)

const situacao = computed(() => {
  void tempoReal.versao
  if (!tempoReal.conectado) return { classe: 'off', texto: 'WebSocket desconectado' }
  if (tempoReal.semDados()) return { classe: 'aviso', texto: 'Conectado, sem dados do simulador' }
  return { classe: 'ok', texto: 'Ao vivo' }
})

function sair(): void {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <RouterView v-if="naTelaDeLogin" />

  <div v-else class="casca">
    <aside class="lateral">
      <div class="marca">
        <span class="icone" aria-hidden="true">🧯</span>
        <div>
          <strong>Gas-Guard</strong>
          <small>AIoT da cozinha</small>
        </div>
      </div>

      <nav>
        <div v-for="grupo in MENU" :key="grupo.secao" class="grupo">
          <p class="secao">{{ grupo.secao }}</p>
          <template v-for="link in grupo.links" :key="link.para">
            <RouterLink v-if="!link.papel || auth.pode(link.papel)" :to="link.para" class="link">
              {{ link.texto }}
            </RouterLink>
          </template>
        </div>
      </nav>
    </aside>

    <div class="principal">
      <header class="topo">
        <h1>{{ rota.meta.titulo ?? 'Gas-Guard' }}</h1>
        <div class="direita">
          <span class="ao-vivo" :data-situacao="situacao.classe">{{ situacao.texto }}</span>
          <span v-if="auth.usuario" class="usuario">
            {{ auth.usuario.nome }}
            <span class="papel">{{ ROTULO_PAPEL[auth.usuario.papel] }}</span>
          </span>
          <button type="button" class="gg-btn gg-btn--mini" @click="sair">Sair</button>
        </div>
      </header>

      <main>
        <RouterView />
      </main>
    </div>
  </div>
</template>

<style scoped>
.casca {
  display: grid;
  grid-template-columns: 13.5rem minmax(0, 1fr);
  min-height: 100vh;
}

.lateral {
  background: #12201f;
  color: #d9e6e4;
  padding: 1.2rem 0.9rem;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}

.marca {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0 0.4rem 1.2rem;
}
.marca .icone {
  font-size: 1.6rem;
}
.marca strong {
  display: block;
  font-size: 1.05rem;
  color: #fff;
}
.marca small {
  color: #8fa9a6;
  font-size: 0.75rem;
}

.grupo {
  margin-bottom: 1rem;
}
.secao {
  margin: 0 0 0.35rem;
  padding: 0 0.5rem;
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #7f9896;
}
.link {
  display: block;
  padding: 0.38rem 0.6rem;
  border-radius: 5px;
  color: #d9e6e4;
  text-decoration: none;
  font-size: 0.9rem;
}
.link:hover {
  background: rgba(255, 255, 255, 0.06);
}
.link.router-link-exact-active {
  background: #24403d;
  color: #fff;
}

.principal {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topo {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 0.9rem 1.6rem;
  border-bottom: 1px solid var(--gg-line);
  background: var(--gg-surface);
  position: sticky;
  top: 0;
  z-index: 5;
}
.topo h1 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 600;
}
.direita {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  flex-wrap: wrap;
}
.usuario {
  font-size: 0.88rem;
  color: var(--gg-ink-2);
}
.papel {
  margin-left: 0.3rem;
  padding: 0.08rem 0.45rem;
  border-radius: 4px;
  background: var(--gg-surface-2);
  border: 1px solid var(--gg-line);
  font-size: 0.75rem;
  color: var(--gg-ink);
}
.ao-vivo {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  color: var(--gg-ink-2);
}
.ao-vivo::before {
  content: '';
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 50%;
  background: var(--gg-ink-2);
}
.ao-vivo[data-situacao='ok']::before {
  background: var(--gg-ok);
  box-shadow: 0 0 0 3px rgba(46, 125, 91, 0.2);
}
.ao-vivo[data-situacao='aviso']::before {
  background: var(--gg-warn);
}
.ao-vivo[data-situacao='off']::before {
  background: var(--gg-crit);
}

main {
  padding: 1.4rem 1.6rem 3rem;
  min-width: 0;
}

@media (max-width: 760px) {
  .casca {
    grid-template-columns: 1fr;
  }
  .lateral {
    position: static;
    height: auto;
  }
  nav {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  main {
    padding: 1rem;
  }
}
</style>
