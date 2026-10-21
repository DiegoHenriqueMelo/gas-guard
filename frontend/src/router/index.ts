import { createRouter, createWebHistory } from 'vue-router'

import type { Papel } from '../api/types'
import { useAuth } from '../stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    publica?: boolean
    papel?: Papel
    titulo?: string
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { publica: true } },
    { path: '/', name: 'painel', component: () => import('../views/PainelView.vue'), meta: { titulo: 'Painel' } },
    { path: '/gemeo', name: 'gemeo', component: () => import('../views/GemeoView.vue'), meta: { titulo: 'Gêmeo digital' } },
    { path: '/insights', name: 'insights', component: () => import('../views/InsightsView.vue'), meta: { titulo: 'Insights' } },
    { path: '/laboratorio', name: 'laboratorio', component: () => import('../views/LaboratorioView.vue'), meta: { titulo: 'Laboratório de dados' } },
    { path: '/treinamento', name: 'treinamento', component: () => import('../views/TreinamentoView.vue'), meta: { titulo: 'Treinamento' } },
    { path: '/assistente', name: 'assistente', component: () => import('../views/AssistenteView.vue'), meta: { titulo: 'Assistente' } },
    { path: '/mensageria', name: 'mensageria', component: () => import('../views/MensageriaView.vue'), meta: { titulo: 'Mensageria' } },
    { path: '/dispositivos', name: 'dispositivos', component: () => import('../views/DispositivosView.vue'), meta: { titulo: 'Dispositivos' } },
    { path: '/ambientes', name: 'ambientes', component: () => import('../views/AmbientesView.vue'), meta: { titulo: 'Ambientes' } },
    { path: '/regras', name: 'regras', component: () => import('../views/RegrasView.vue'), meta: { titulo: 'Regras e limites' } },
    { path: '/auditoria', name: 'auditoria', component: () => import('../views/AuditoriaView.vue'), meta: { titulo: 'Auditoria', papel: 'administrador' } },
    { path: '/infraestrutura', name: 'infraestrutura', component: () => import('../views/InfraView.vue'), meta: { titulo: 'Infraestrutura' } },
    // Qualquer rota desconhecida volta para o painel. O nginx ja devolve o
    // index.html para qualquer caminho (try_files); quem decide e o router.
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// Sem login, so a tela de login. Pagina de administrador para outro papel
// volta ao painel. (A protecao de verdade e o backend: 401/403.)
router.beforeEach((destino) => {
  const auth = useAuth()
  if (!destino.meta.publica && !auth.logado) return { name: 'login', query: { volta: destino.fullPath } }
  if (destino.name === 'login' && auth.logado) return { name: 'painel' }
  if (destino.meta.papel && !auth.pode(destino.meta.papel)) return { name: 'painel' }
  return true
})

export default router
