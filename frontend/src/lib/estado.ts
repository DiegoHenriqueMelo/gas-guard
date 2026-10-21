/**
 * De onde vem a COR de cada dispositivo (painel e cena 3D).
 *
 *   sensor       -> faixa normal do cadastro (a mesma conta do backend,
 *                   Dispositivo.classificar) + alertas abertos
 *   equipamento  -> saude prevista pela IA + estado do motor + alertas
 *   atuador      -> valvula fechada = atencao, sirene ligada = critico
 *   qualquer um  -> "sem_dados" se nao chegou leitura nos ultimos 8 s
 */
import type { Alerta, ConteudoInsight, Dispositivo, Estado } from '../api/types'
import type { UltimaLeitura } from '../stores/tempoReal'

const ORDEM: Record<Estado, number> = { sem_dados: -1, normal: 0, atencao: 1, critico: 2 }

export function pior(...estados: Estado[]): Estado {
  return estados.reduce((a, b) => (ORDEM[b] > ORDEM[a] ? b : a), 'normal' as Estado)
}

export function classificarValor(d: Dispositivo, valor: number | undefined): Estado {
  if (valor === undefined || Number.isNaN(valor)) return 'sem_dados'
  if (d.critico_min !== null && valor < d.critico_min) return 'critico'
  if (d.critico_max !== null && valor >= d.critico_max) return 'critico'
  if (d.normal_min !== null && valor < d.normal_min) return 'atencao'
  if (d.normal_max !== null && valor >= d.normal_max) return 'atencao'
  return 'normal'
}

export function estadoDoDispositivo(
  d: Dispositivo,
  leitura: UltimaLeitura | undefined,
  insight: ConteudoInsight | undefined,
  alertas: Alerta[],
  semDados: boolean,
): Estado {
  if (semDados || !leitura) return 'sem_dados'

  const doAlerta: Estado = alertas.some((a) => a.dispositivo_codigo === d.codigo && a.severidade === 'critico')
    ? 'critico'
    : alertas.some((a) => a.dispositivo_codigo === d.codigo)
      ? 'atencao'
      : 'normal'

  if (d.categoria === 'atuador') {
    if (leitura.estado === 'ligado' && d.tipo === 'sirene') return 'critico'
    if (leitura.estado === 'fechada') return 'atencao'
    return 'normal'
  }

  const daFaixa = d.campo_principal ? classificarValor(d, leitura.leituras[d.campo_principal]) : 'normal'

  if (d.categoria === 'equipamento') {
    if (leitura.estado === 'falha') return 'critico'
    let daIa: Estado = 'normal'
    if (insight?.estado_ia === 'ok' && typeof insight.saude === 'number') {
      daIa = insight.saude < 30 ? 'critico' : insight.saude < 60 ? 'atencao' : 'normal'
    }
    return pior(daFaixa === 'sem_dados' ? 'normal' : daFaixa, daIa, doAlerta)
  }

  return pior(daFaixa === 'sem_dados' ? 'normal' : daFaixa, doAlerta)
}

/** Cores do estado, as mesmas no CSS (--gg-*) e na cena 3D. */
export const COR_ESTADO: Record<Estado, string> = {
  normal: '#2e8a5f',
  atencao: '#c98a1b',
  critico: '#c0392b',
  sem_dados: '#8a9896',
}
