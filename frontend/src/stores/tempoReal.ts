/**
 * Tudo o que chega pelo WebSocket passa por aqui.
 *
 * Dois jeitos de guardar, de proposito:
 *
 * - `bruto`: objeto comum (markRaw), SEM reatividade do Vue. E o que a cena
 *   3D le dentro do loop de animacao, 60 vezes por segundo. Se cada
 *   mensagem disparasse a reatividade do Vue, a cena seria redesenhada a
 *   cada leitura - o enunciado pede exatamente o contrario.
 * - `versao`: um contador reativo que sobe no maximo 4 vezes por segundo.
 *   Os componentes de tela (cartoes, graficos) dependem dele e releem o
 *   `bruto` quando ele muda.
 */
import { defineStore } from 'pinia'
import { markRaw, ref } from 'vue'

import { pedirTicket } from '../api/client'
import type { ConteudoInsight, ConteudoTelemetria, Envelope } from '../api/types'

const PONTOS_POR_SERIE = 150 // 5 min de leituras a cada 2 s
export const LIMITE_SEM_DADOS_MS = 8000

export interface UltimaLeitura {
  instante: string
  recebidoEm: number
  leituras: Record<string, number>
  estado: string | null
  zona: string
  tipo: string
}

export interface Serie {
  t: number[]
  v: number[]
}

export interface Evento {
  id: string
  instante: string
  tipo: string
  texto: string
  severidade?: string
}

export interface Bruto {
  telemetria: Record<string, UltimaLeitura>
  series: Record<string, Record<string, Serie>>
  insights: Record<string, ConteudoInsight & { instante: string }>
  seriesSaude: Record<string, Serie>
  ultimaTelemetria: number
}

function empurrar(serie: Serie, t: number, v: number): void {
  serie.t.push(t)
  serie.v.push(v)
  if (serie.t.length > PONTOS_POR_SERIE) {
    serie.t.shift()
    serie.v.shift()
  }
}

export const useTempoReal = defineStore('tempoReal', () => {
  const bruto: Bruto = markRaw({
    telemetria: {},
    series: {},
    insights: {},
    seriesSaude: {},
    ultimaTelemetria: 0,
  })

  const versao = ref(0)
  const conectado = ref(false)
  const eventos = ref<Evento[]>([])
  // contadores: quem lista alertas/jobs/modelos observa e recarrega
  const alertasMudaram = ref(0)
  const jobsMudaram = ref(0)
  const modelosMudaram = ref(0)
  const progressoJobs = ref<Record<number, Record<string, unknown>>>({})

  let ws: WebSocket | null = null
  let encerrado = false
  let pendente = false
  let tentativa = 0

  function avisar(): void {
    // agrupa as mudancas: no maximo uma atualizacao de tela a cada 250 ms
    if (pendente) return
    pendente = true
    setTimeout(() => {
      pendente = false
      versao.value++
    }, 250)
  }

  function registrarEvento(evento: Evento): void {
    eventos.value = [evento, ...eventos.value].slice(0, 40)
  }

  function guardarTelemetria(env: Envelope<ConteudoTelemetria>, agora: number): void {
    if (!env.dispositivo) return
    const c = env.conteudo
    const anterior = bruto.telemetria[env.dispositivo]
    // a mensagem "so estado" (logo depois de um comando) nao traz leituras:
    // mantem as ultimas que ja tinhamos
    bruto.telemetria[env.dispositivo] = {
      instante: env.instante,
      recebidoEm: agora,
      leituras: Object.keys(c.leituras ?? {}).length ? c.leituras : (anterior?.leituras ?? {}),
      estado: c.estado ?? anterior?.estado ?? null,
      zona: c.zona,
      tipo: c.tipo,
    }
    bruto.ultimaTelemetria = agora
    const series = (bruto.series[env.dispositivo] ??= {})
    const t = Date.parse(env.instante)
    for (const [campo, valor] of Object.entries(c.leituras ?? {})) {
      if (typeof valor === 'number') empurrar((series[campo] ??= { t: [], v: [] }), t, valor)
    }
    if (c.estado) {
      const acionado = c.estado === 'ligado' || c.estado === 'aberta' ? 1 : 0
      empurrar((series.acionado ??= { t: [], v: [] }), t, acionado)
    }
  }

  function aoReceber(texto: string): void {
    const agora = Date.now()
    const msg = JSON.parse(texto) as Envelope<Record<string, unknown>>

    if (msg.tipo === 'snapshot') {
      const conteudo = msg.conteudo as {
        telemetria: Record<string, Envelope<ConteudoTelemetria>>
        insights: Record<string, Envelope<ConteudoInsight>>
      }
      for (const env of Object.values(conteudo.telemetria)) {
        // o snapshot pode ser velho: so conta como "ao vivo" se for recente
        const idade = agora - Date.parse(env.instante)
        guardarTelemetria(env, idade < LIMITE_SEM_DADOS_MS ? agora : agora - idade)
      }
      for (const env of Object.values(conteudo.insights)) {
        if (env.dispositivo) bruto.insights[env.dispositivo] = { ...env.conteudo, instante: env.instante }
      }
      avisar()
      return
    }

    switch (msg.tipo) {
      case 'telemetria':
        guardarTelemetria(msg as unknown as Envelope<ConteudoTelemetria>, agora)
        break
      case 'insight': {
        const c = msg.conteudo as unknown as ConteudoInsight
        if (msg.dispositivo) {
          bruto.insights[msg.dispositivo] = { ...c, instante: msg.instante }
          if (typeof c.saude === 'number') {
            empurrar((bruto.seriesSaude[msg.dispositivo] ??= { t: [], v: [] }), Date.parse(msg.instante), c.saude)
          }
        }
        break
      }
      case 'alerta': {
        const c = msg.conteudo as Record<string, string>
        alertasMudaram.value++
        if (c.acao === 'abrir' && c.mensagem) {
          registrarEvento({ id: msg.id, instante: msg.instante, tipo: 'alerta', texto: c.mensagem, severidade: c.severidade })
        } else if (c.acao === 'fechar') {
          registrarEvento({ id: msg.id, instante: msg.instante, tipo: 'alerta', texto: `Alerta encerrado: ${msg.dispositivo} (${c.chave})` })
        }
        break
      }
      case 'comando': {
        const c = msg.conteudo as Record<string, unknown>
        const origem = String(c.origem ?? '')
        const quem = origem === 'web' ? `por ${c.usuario}` : origem.startsWith('regra') ? 'pela regra' : origem
        registrarEvento({ id: msg.id, instante: msg.instante, tipo: 'comando', texto: `${c.acao} → ${msg.dispositivo} (${quem})` })
        break
      }
      case 'acionamento': {
        const c = msg.conteudo as Record<string, unknown>
        registrarEvento({
          id: msg.id, instante: msg.instante, tipo: 'acionamento',
          texto: `Regra "${c.regra}": ${c.gatilho} ${c.campo} = ${c.valor} (${c.condicao}) → ${c.acao} ${c.alvo}`,
        })
        break
      }
      case 'progresso': {
        const c = msg.conteudo as Record<string, unknown>
        progressoJobs.value = { ...progressoJobs.value, [Number(c.job_id)]: c }
        if (c.status === 'concluido' || c.status === 'falhou') {
          jobsMudaram.value++
          registrarEvento({ id: msg.id, instante: msg.instante, tipo: 'job', texto: `Job ${c.job_id} (${c.tipo}) ${c.status}` })
        }
        break
      }
      case 'modelo':
        modelosMudaram.value++
        registrarEvento({
          id: msg.id, instante: msg.instante, tipo: 'modelo',
          texto: `Modelo ${(msg.conteudo as Record<string, unknown>).versao} em uso`,
        })
        break
    }
    avisar()
  }

  async function conectar(): Promise<void> {
    encerrado = false
    if (ws && ws.readyState <= WebSocket.OPEN) return
    let ticket: string
    try {
      ticket = await pedirTicket()
    } catch {
      agendarReconexao()
      return
    }
    const protocolo = location.protocol === 'https:' ? 'wss' : 'ws'
    // o JWT nao vai na URL: so um ticket que vale 30 s e uma vez
    ws = new WebSocket(`${protocolo}://${location.host}/ws?ticket=${encodeURIComponent(ticket)}`)
    ws.onopen = () => {
      conectado.value = true
      tentativa = 0
    }
    ws.onmessage = (evento) => aoReceber(evento.data)
    ws.onclose = () => {
      conectado.value = false
      ws = null
      if (!encerrado) agendarReconexao()
    }
  }

  function agendarReconexao(): void {
    tentativa++
    setTimeout(conectar, Math.min(1000 * 2 ** tentativa, 10000))
  }

  function desconectar(): void {
    encerrado = true
    ws?.close()
    ws = null
  }

  // sem mensagem nenhuma a tela tambem precisa mudar ("sem dados")
  setInterval(() => versao.value++, 1000)

  function semDados(codigo?: string): boolean {
    const quando = codigo ? bruto.telemetria[codigo]?.recebidoEm : bruto.ultimaTelemetria
    return !quando || Date.now() - quando > LIMITE_SEM_DADOS_MS
  }

  return {
    bruto,
    versao,
    conectado,
    eventos,
    alertasMudaram,
    jobsMudaram,
    modelosMudaram,
    progressoJobs,
    conectar,
    desconectar,
    semDados,
  }
})
