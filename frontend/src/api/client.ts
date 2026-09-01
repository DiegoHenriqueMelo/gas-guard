import axios from 'axios'

import type {
  Ambiente,
  AmbienteCreate,
  AmbienteUpdate,
  Dispositivo,
  DispositivoCreate,
  DispositivoUpdate,
  Leitura,
} from './types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
  timeout: 8000,
})

/**
 * Traduz o erro do axios na frase que vai para a tela.
 *
 * O backend responde `{"detail": "..."}` nos erros que ele mesmo levanta
 * (404, 409) e `{"detail": [{loc, msg, ...}]}` na validacao do Pydantic
 * (422). Sem tratar os dois formatos, o 422 apareceria como [object Object].
 */
export function mensagemDeErro(causa: unknown): string {
  if (axios.isAxiosError(causa)) {
    const detalhe = causa.response?.data?.detail

    if (typeof detalhe === 'string') return detalhe

    if (Array.isArray(detalhe)) {
      return detalhe
        .map((item) => item?.msg ?? 'campo inválido')
        .join('; ')
    }

    if (causa.response) return `Erro ${causa.response.status}`

    return 'Não foi possível falar com a API. Ela está no ar?'
  }

  if (causa instanceof Error) return causa.message

  return 'Erro desconhecido'
}

// ---------- ambientes ----------

export async function listarAmbientes(): Promise<Ambiente[]> {
  const { data } = await api.get<Ambiente[]>('/api/ambientes')
  return data
}

export async function criarAmbiente(dados: AmbienteCreate): Promise<Ambiente> {
  const { data } = await api.post<Ambiente>('/api/ambientes', dados)
  return data
}

export async function editarAmbiente(
  id: number,
  dados: AmbienteUpdate,
): Promise<Ambiente> {
  const { data } = await api.patch<Ambiente>(`/api/ambientes/${id}`, dados)
  return data
}

export async function excluirAmbiente(id: number): Promise<Ambiente> {
  const { data } = await api.delete<Ambiente>(`/api/ambientes/${id}`)
  return data
}

// ---------- dispositivos ----------

export async function listarDispositivos(): Promise<Dispositivo[]> {
  const { data } = await api.get<Dispositivo[]>('/api/dispositivos')
  return data
}

export async function buscarDispositivo(codigo: string): Promise<Dispositivo> {
  const { data } = await api.get<Dispositivo>(`/api/dispositivos/${codigo}`)
  return data
}

export async function criarDispositivo(
  dados: DispositivoCreate,
): Promise<Dispositivo> {
  const { data } = await api.post<Dispositivo>('/api/dispositivos', dados)
  return data
}

export async function editarDispositivo(
  codigo: string,
  dados: DispositivoUpdate,
): Promise<Dispositivo> {
  const { data } = await api.patch<Dispositivo>(
    `/api/dispositivos/${codigo}`,
    dados,
  )
  return data
}

/** Exclusao logica: o backend apenas marca `ativo = false`. */
export async function desativarDispositivo(
  codigo: string,
): Promise<Dispositivo> {
  const { data } = await api.delete<Dispositivo>(`/api/dispositivos/${codigo}`)
  return data
}

// ---------- leituras ----------

export async function buscarHistorico(
  codigo: string,
  minutos = 60,
): Promise<Leitura[]> {
  const { data } = await api.get<Leitura[]>(`/api/leituras/${codigo}`, {
    params: { minutos },
  })
  return data
}
