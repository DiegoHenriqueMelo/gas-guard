import { createRouter, createWebHistory } from 'vue-router'

import AmbientesView from '../views/AmbientesView.vue'
import DashboardView from '../views/DashboardView.vue'
import DispositivosView from '../views/DispositivosView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'painel',
      component: DashboardView,
    },
    {
      path: '/ambientes',
      name: 'ambientes',
      component: AmbientesView,
    },
    {
      path: '/dispositivos',
      name: 'dispositivos',
      component: DispositivosView,
    },
    {
      // Qualquer rota desconhecida volta para o painel. O nginx ja devolve
      // o index.html para qualquer caminho (try_files), entao quem decide
      // o que fazer com uma URL invalida e o router, aqui.
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})
