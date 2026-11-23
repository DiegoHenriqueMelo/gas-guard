/** Cadastro (dispositivos, ambientes) e alertas abertos, compartilhados
 *  entre as telas. Recarrega sozinho quando um alerta muda pelo WebSocket. */
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

import { listarAlertas, listarAmbientes, listarDispositivos } from '../api/client'
import type { Alerta, Ambiente, Dispositivo } from '../api/types'
import { useTempoReal } from './tempoReal'

export const useCadastro = defineStore('cadastro', () => {
  const dispositivos = ref<Dispositivo[]>([])
  const ambientes = ref<Ambiente[]>([])
  const alertas = ref<Alerta[]>([])
  const carregado = ref(false)

  const ativos = computed(() => dispositivos.value.filter((d) => d.ativo))
  const porCodigo = computed(() => Object.fromEntries(dispositivos.value.map((d) => [d.codigo, d])))

  async function carregar(): Promise<void> {
    const [d, a, al] = await Promise.all([listarDispositivos(), listarAmbientes(), listarAlertas(true)])
    dispositivos.value = d
    ambientes.value = a
    alertas.value = al
    carregado.value = true
  }

  async function recarregarAlertas(): Promise<void> {
    alertas.value = await listarAlertas(true)
  }

  const tempoReal = useTempoReal()
  let espera: ReturnType<typeof setTimeout> | undefined
  watch(
    () => tempoReal.alertasMudaram,
    () => {
      // o alerta e gravado pelo servico regras um instante depois do evento
      clearTimeout(espera)
      espera = setTimeout(() => recarregarAlertas().catch(() => {}), 600)
    },
  )

  return { dispositivos, ambientes, alertas, carregado, ativos, porCodigo, carregar, recarregarAlertas }
})
