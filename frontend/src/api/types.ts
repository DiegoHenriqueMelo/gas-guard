// Espelho dos schemas Pydantic do backend. Manter os dois em sincronia:
// quando um campo entra num *Read do backend, entra aqui.

export type Papel = 'visualizador' | 'operador' | 'administrador'

export interface UsuarioToken {
  usuario: string
  papel: Papel
  nome: string
}

export interface Ambiente {
  id: number
  nome: string
  zona: string
  descricao: string | null
  criado_em: string
}

export type Categoria = 'sensor' | 'atuador' | 'equipamento'

export interface Dispositivo {
  id: number
  codigo: string
  nome: string
  ativo: boolean
  ambiente_id: number
  categoria: Categoria
  tipo: string
  campo_principal: string | null
  unidade: string | null
  controlavel: boolean
  normal_min: number | null
  normal_max: number | null
  critico_min: number | null
  critico_max: number | null
  ultimo_contato: string | null
  criado_em: string
}

/** O envelope unico que trafega no RabbitMQ e chega pelo WebSocket. */
export interface Envelope<C = Record<string, unknown>> {
  rk?: string
  id: string
  instante: string
  tipo: string
  dispositivo: string | null
  conteudo: C
}

export interface ConteudoTelemetria {
  zona: string
  tipo: string
  leituras: Record<string, number>
  estado: string | null
}

export interface ConteudoInsight {
  zona: string
  tipo: string
  versao_modelo: string | null
  estado_operacao: string
  estado_ia: 'ok' | 'aquecendo' | 'sem_modelo' | 'parado' | 'falha'
  saude?: number
  rul_horas?: number
  tendencia?: 'piorando' | 'estavel' | 'melhorando' | 'falhou'
  inclinacao_saude?: number
  amostras?: number
  faltam?: number
  alertas?: Record<string, string | null>
}

export interface Alerta {
  id: number
  dispositivo_codigo: string
  chave: string
  origem: string
  severidade: 'atencao' | 'critico'
  mensagem: string
  valor: number | null
  ativo: boolean
  aberto_em: string
  atualizado_em: string
  fechado_em: string | null
}

export interface Regra {
  id: number
  nome: string
  ativa: boolean
  dispositivo_codigo: string
  campo: string
  operador: string
  limite: number
  alvo_codigo: string
  acao: string
  criado_em: string
}

export interface Job {
  id: number
  tipo: 'gerar' | 'treinar'
  status: 'na_fila' | 'executando' | 'concluido' | 'falhou'
  parametros: Record<string, unknown>
  progresso: number
  etapa: string | null
  resultado: Record<string, unknown> | null
  erro: string | null
  usuario: string | null
  criado_em: string
  iniciado_em: string | null
  concluido_em: string | null
}

export interface Metricas {
  mae: number
  rmse: number
  r2: number
}

export interface AvaliacaoAlvo {
  modelo: Metricas
  base: Metricas
  linhas: number
}

export interface ResultadoAlvo {
  nome: string
  unidade: string
  limites: [number, number]
  avaliacao: Record<'validacao' | 'teste' | 'teste_degradando', AvaliacaoAlvo>
  venceu_base: boolean
  ganho_sobre_base_pct: number
  importancia: [string, number][]
  dispersao: [number, number][]
}

export interface ModeloResumo {
  id: number
  versao: string
  job_id: number | null
  dataset_job_id: number | null
  venceu_base: boolean
  ativo: boolean
  criado_em: string
}

export interface ModeloDetalhe extends ModeloResumo {
  metricas: {
    versao: string
    venceu_base: boolean
    alvos: Record<string, ResultadoAlvo>
    dados: {
      dataset: string
      linhas_usadas: number
      maquinas: Record<string, number>
      maquinas_teste: number[]
      features: number
      janelas: Record<string, number>
    }
    segundos: number
  }
}

export interface Configuracao {
  chave: string
  valor: number
  descricao: string
  atualizado_em: string
}

export interface RegistroAuditoria {
  id: number
  instante: string
  usuario: string | null
  papel: string | null
  acao: string
  detalhe: Record<string, unknown>
  ip: string | null
  sucesso: boolean
}

export type Estado = 'normal' | 'atencao' | 'critico' | 'sem_dados'

export const ROTULO_ESTADO: Record<Estado, string> = {
  normal: 'Normal',
  atencao: 'Atenção',
  critico: 'Crítico',
  sem_dados: 'Sem dados',
}

// ---------- corpos de requisicao ----------

export interface AmbienteCreate {
  nome: string
  zona?: string | null
  descricao: string | null
}

export interface AmbienteUpdate {
  nome?: string
  zona?: string
  descricao?: string | null
}

export interface DispositivoCreate {
  codigo: string
  nome: string
  ambiente_id: number
  tipo: string
  normal_min?: number | null
  normal_max?: number | null
  critico_min?: number | null
  critico_max?: number | null
}

export interface DispositivoUpdate {
  nome?: string
  ativo?: boolean
  ambiente_id?: number
  normal_min?: number | null
  normal_max?: number | null
  critico_min?: number | null
  critico_max?: number | null
}
