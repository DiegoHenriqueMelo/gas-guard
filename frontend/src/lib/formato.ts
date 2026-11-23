const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 })
const formatadores = new Map<number, Intl.NumberFormat>()

export function fmt(valor: number | null | undefined, casas = 1): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return '—'
  if (!formatadores.has(casas)) {
    formatadores.set(casas, new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: casas }))
  }
  // + 0 transforma -0 em 0 (R² da base simples costuma dar -0,000...)
  return formatadores.get(casas)!.format(Number(valor.toFixed(casas)) + 0)
}

export function fmtMil(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return '—'
  return inteiro.format(valor)
}

export function hora(iso: string | number): string {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function dataHora(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'medium' })
}

export function haQuanto(iso: string | null | undefined): string {
  if (!iso) return 'nunca'
  const segundos = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (segundos < 5) return 'agora'
  if (segundos < 60) return `há ${segundos} s`
  if (segundos < 3600) return `há ${Math.floor(segundos / 60)} min`
  if (segundos < 86400) return `há ${Math.floor(segundos / 3600)} h`
  return dataHora(iso)
}

/** Nome legivel dos campos que chegam do simulador. */
export const ROTULO_CAMPO: Record<string, string> = {
  ppm: 'Gás',
  temperatura: 'Temperatura',
  umidade: 'Umidade',
  lux: 'Luminosidade',
  vazao: 'Vazão',
  vibracao: 'Vibração',
  corrente: 'Corrente',
  rpm: 'Rotação',
  acionado: 'Acionado',
}

export const UNIDADE_CAMPO: Record<string, string> = {
  ppm: 'ppm',
  temperatura: '°C',
  umidade: '%',
  lux: 'lx',
  vazao: 'm³/h',
  vibracao: 'mm/s',
  corrente: 'A',
  rpm: 'rpm',
}

export const ROTULO_ACAO: Record<string, string> = {
  ligar: 'Ligar',
  desligar: 'Desligar',
  abrir: 'Abrir',
  fechar: 'Fechar',
}

export const ACOES_POR_TIPO: Record<string, string[]> = {
  exaustor: ['ligar', 'desligar'],
  valvula: ['abrir', 'fechar'],
  sirene: ['ligar', 'desligar'],
}
