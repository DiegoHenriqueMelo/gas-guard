// Espelho dos schemas Pydantic do backend. Manter os dois em sincronia:
// quando um campo entra no AmbienteRead/DispositivoRead/LeituraOut, entra aqui.

export interface Ambiente {
  id: number
  nome: string
  descricao: string | null
  criado_em: string
}

export interface Dispositivo {
  id: number
  codigo: string
  nome: string
  ativo: boolean
  ambiente_id: number
  ultimo_contato: string | null
  criado_em: string
}

export interface Leitura {
  horario: string
  ppm: number
}

export type Nivel = 'normal' | 'atencao' | 'critico'

// Faixas de concentracao. O GLP tem limite inferior de explosividade (LEL)
// perto de 19000 ppm; 2000 ppm e cerca de 10% do LEL, o ponto onde a norma
// costuma mandar alarmar. O mesmo valor esta no firmware, em LIMITE_PPM.
export const LIMITE_ATENCAO = 1000
export const LIMITE_CRITICO = 2000

export function classificar(ppm: number): Nivel {
  if (ppm >= LIMITE_CRITICO) return 'critico'
  if (ppm >= LIMITE_ATENCAO) return 'atencao'
  return 'normal'
}

export const ROTULO_NIVEL: Record<Nivel, string> = {
  normal: 'Normal',
  atencao: 'Atenção',
  critico: 'Crítico',
}

// ---------- corpos de requisicao ----------
// Espelham AmbienteCreate/Update e DispositivoCreate/Update do backend.
// Os campos opcionais do PATCH sao opcionais aqui tambem: o service usa
// model_dump(exclude_unset=True), entao o que nao for enviado nao e tocado.

export interface AmbienteCreate {
  nome: string
  descricao: string | null
}

export interface AmbienteUpdate {
  nome?: string
  descricao?: string | null
}

export interface DispositivoCreate {
  codigo: string
  nome: string
  ambiente_id: number
}

export interface DispositivoUpdate {
  nome?: string
  ativo?: boolean
  ambiente_id?: number
}
