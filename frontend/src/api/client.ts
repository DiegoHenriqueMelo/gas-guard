import axios from 'axios'

import type {
  Alerta,
  Ambiente,
  AmbienteCreate,
  AmbienteUpdate,
  Configuracao,
  Dispositivo,
  DispositivoCreate,
  DispositivoUpdate,
  Envelope,
  Job,
  ModeloDetalhe,
  ModeloResumo,
  Regra,
  RegistroAuditoria,
  UsuarioToken,
} from './types'

// Mesma origem do Vue: em producao o nginx repassa /api para a API; no
// `npm run dev` quem repassa e o proxy do Vite (vite.config.ts).
export const api = axios.create({ baseURL: '/', timeout: 15000 })

const CHAVE_SESSAO = 'gasguard-sessao'

export function lerSessao(): { token: string; usuario: UsuarioToken } | null {
  try {
    const texto = sessionStorage.getItem(CHAVE_SESSAO)
    return texto ? JSON.parse(texto) : null
  } catch {
    return null
  }
}

export function gravarSessao(sessao: { token: string; usuario: UsuarioToken } | null): void {
  try {
    if (sessao) sessionStorage.setItem(CHAVE_SESSAO, JSON.stringify(sessao))
    else sessionStorage.removeItem(CHAVE_SESSAO)
  } catch {
    // aba anonima com storage bloqueado: a sessao vale so ate o F5
  }
}

// Todo request leva o JWT no cabecalho Authorization.
api.interceptors.request.use((config) => {
  const sessao = lerSessao()
  if (sessao) config.headers.Authorization = `Bearer ${sessao.token}`
  return config
})

// Token vencido ou invalido: volta para a tela de login.
api.interceptors.response.use(
  (resposta) => resposta,
  (erro) => {
    if (axios.isAxiosError(erro) && erro.response?.status === 401 && lerSessao()) {
      gravarSessao(null)
      window.location.assign('/login')
    }
    return Promise.reject(erro)
  },
)

/**
 * Traduz o erro do axios na frase que vai para a tela.
 *
 * O backend responde `{"detail": "..."}` nos erros que ele mesmo levanta
 * e `{"detail": [{loc, msg, ...}]}` na validacao do Pydantic (422).
 */
export function mensagemDeErro(causa: unknown): string {
  if (axios.isAxiosError(causa)) {
    const detalhe = causa.response?.data?.detail
    if (typeof detalhe === 'string') return detalhe
    if (Array.isArray(detalhe)) {
      return detalhe.map((item) => item?.msg ?? 'campo inválido').join('; ')
    }
    if (causa.response) return `Erro ${causa.response.status}`
    return 'Não foi possível falar com a API. Ela está no ar?'
  }
  if (causa instanceof Error) return causa.message
  return 'Erro desconhecido'
}

// ---------- autenticacao ----------

export async function entrar(usuario: string, senha: string) {
  const { data } = await api.post<{ token: string; usuario: UsuarioToken }>(
    '/api/auth/login',
    { usuario, senha },
  )
  return data
}

export async function pedirTicket(): Promise<string> {
  const { data } = await api.post<{ ticket: string }>('/api/ws/ticket')
  return data.ticket
}

// ---------- cadastro ----------

export const listarAmbientes = async () => (await api.get<Ambiente[]>('/api/ambientes')).data
export const criarAmbiente = async (dados: AmbienteCreate) =>
  (await api.post<Ambiente>('/api/ambientes', dados)).data
export const editarAmbiente = async (id: number, dados: AmbienteUpdate) =>
  (await api.patch<Ambiente>(`/api/ambientes/${id}`, dados)).data
export const excluirAmbiente = async (id: number) =>
  (await api.delete<Ambiente>(`/api/ambientes/${id}`)).data

export const listarDispositivos = async () =>
  (await api.get<Dispositivo[]>('/api/dispositivos')).data
export const criarDispositivo = async (dados: DispositivoCreate) =>
  (await api.post<Dispositivo>('/api/dispositivos', dados)).data
export const editarDispositivo = async (codigo: string, dados: DispositivoUpdate) =>
  (await api.patch<Dispositivo>(`/api/dispositivos/${codigo}`, dados)).data
/** Exclusao logica: o backend apenas marca `ativo = false`. */
export const desativarDispositivo = async (codigo: string) =>
  (await api.delete<Dispositivo>(`/api/dispositivos/${codigo}`)).data

// ---------- comandos (Web -> IoT) ----------

export const comandar = async (codigo: string, acao: string) =>
  (await api.post(`/api/dispositivos/${codigo}/comandos`, { acao })).data

export const comandarSimulador = async (comando: Record<string, unknown>) =>
  (await api.post('/api/simulador/comandos', { comando })).data

// ---------- series temporais ----------

export type Ponto = { horario: string } & Record<string, number | string>

export const historico = async (codigo: string, minutos: number) =>
  (await api.get<Ponto[]>(`/api/leituras/${codigo}`, { params: { minutos } })).data

export const historicoInsights = async (codigo: string, minutos: number) =>
  (await api.get<Ponto[]>(`/api/insights/${codigo}/historico`, { params: { minutos } })).data

export const estadoAtual = async () =>
  (await api.get<{ telemetria: Record<string, Envelope>; insights: Record<string, Envelope> }>(
    '/api/estado',
  )).data

// ---------- regras, alertas, auditoria ----------

export const listarRegras = async () => (await api.get<Regra[]>('/api/regras')).data
export const criarRegra = async (dados: Omit<Regra, 'id' | 'criado_em'>) =>
  (await api.post<Regra>('/api/regras', dados)).data
export const editarRegra = async (id: number, dados: Partial<Regra>) =>
  (await api.patch<Regra>(`/api/regras/${id}`, dados)).data
export const excluirRegra = async (id: number) => api.delete(`/api/regras/${id}`)

export const listarAlertas = async (ativos: boolean, limite = 50) =>
  (await api.get<Alerta[]>('/api/alertas', { params: { ativos, limite } })).data

export const listarAuditoria = async (limite = 100, acao?: string) =>
  (await api.get<RegistroAuditoria[]>('/api/auditoria', { params: { limite, acao: acao || undefined } })).data

export const listarConfiguracoes = async () =>
  (await api.get<Configuracao[]>('/api/configuracoes')).data
export const editarConfiguracao = async (chave: string, valor: number) =>
  (await api.put<Configuracao>(`/api/configuracoes/${chave}`, { valor })).data

// ---------- laboratorio e IA ----------

export const opcoesLab = async () => (await api.get('/api/lab/opcoes')).data
export const estimarLab = async (parametros: Record<string, unknown>) =>
  (await api.post<{ leituras: number; max_leituras: number; cabe: boolean }>(
    '/api/lab/estimativa',
    parametros,
  )).data
export const gerarDados = async (parametros: Record<string, unknown>) =>
  (await api.post<Job>('/api/lab/jobs', parametros)).data
export const listarJobs = async (tipo?: 'gerar' | 'treinar') =>
  (await api.get<Job[]>('/api/lab/jobs', { params: { tipo } })).data

export const treinar = async (dataset_job_id: number, max_linhas: number) =>
  (await api.post<Job>('/api/treino/jobs', { dataset_job_id, max_linhas })).data
export const listarModelos = async () => (await api.get<ModeloResumo[]>('/api/modelos')).data
export const detalharModelo = async (versao: string) =>
  (await api.get<ModeloDetalhe>(`/api/modelos/${versao}`)).data
export const ativarModelo = async (versao: string) =>
  (await api.post<ModeloResumo>(`/api/modelos/${versao}/ativar`)).data

// ---------- mensageria e infraestrutura ----------

export const visaoMensageria = async () => (await api.get('/api/mensageria/visao')).data
export const lerDlq = async () => (await api.get('/api/mensageria/dlq')).data
export const esvaziarDlq = async () => api.delete('/api/mensageria/dlq')
export const demonstrarDlq = async () => (await api.post('/api/mensageria/dlq/demonstracao')).data
export const infraestrutura = async () => (await api.get('/api/infra')).data

// ---------- assistente ----------

export const statusAssistente = async () =>
  (await api.get<{ modelo: string; servidor: boolean; baixado: boolean; carregado: boolean }>(
    '/api/assistente/status',
  )).data

/**
 * A resposta do LLM chega em streaming. O axios no navegador nao entrega o
 * corpo aos pedacos, entao aqui usamos fetch() + ReadableStream.
 */
export async function perguntar(
  pergunta: string,
  historicoConversa: { role: 'user' | 'assistant'; content: string }[],
  aoReceber: (pedaco: string) => void,
): Promise<void> {
  const sessao = lerSessao()
  const resposta = await fetch('/api/assistente/perguntar', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: sessao ? `Bearer ${sessao.token}` : '',
    },
    body: JSON.stringify({ pergunta, historico: historicoConversa }),
  })
  if (!resposta.ok || !resposta.body) {
    let detalhe = `Erro ${resposta.status}`
    try {
      detalhe = (await resposta.json()).detail ?? detalhe
    } catch {
      // corpo nao era JSON
    }
    throw new Error(detalhe)
  }
  const leitor = resposta.body.getReader()
  const decodificador = new TextDecoder()
  for (;;) {
    const { done, value } = await leitor.read()
    if (done) break
    aoReceber(decodificador.decode(value, { stream: true }))
  }
}
