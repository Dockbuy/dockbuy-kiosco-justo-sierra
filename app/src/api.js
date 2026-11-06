import {beginTraceRequest,traceResponseOutcome} from './interaction-trace.js'
// El binario Tauri no tiene el proxy de desarrollo de Vite.
const base = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? '/api' : 'http://127.0.0.1:8787/api')).replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status = 0) { super(message); this.name = 'ApiError'; this.status = status }
}

export async function request(path, {method = 'GET', token, body, signal, timeout = 20000} = {}) {
  // Incluso logout debe respetar el contrato JSON de todos los POST.
  if (body === undefined && method.toUpperCase() === 'POST') body = {}
  const controller = new AbortController()
  const cancel = () => controller.abort()
  if (signal?.aborted) controller.abort()
  else signal?.addEventListener('abort', cancel, {once: true})
  let timedOut = false
  const finishTrace=beginTraceRequest(path,body)
  const timer = setTimeout(() => { timedOut = true; controller.abort() }, timeout)
  try {
    const response = await fetch(`${base}${path}`, {
      method, signal: controller.signal, cache: 'no-store',
      headers: {...(body !== undefined ? {'Content-Type': 'application/json'} : {}), ...(token ? {Authorization: `Bearer ${token}`} : {})},
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    let data
    try { data = await response.json() } catch { throw new ApiError('La API devolvió una respuesta inválida.', response.status) }
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new ApiError('Formato de respuesta inválido.', response.status)
    if (!response.ok) throw new ApiError(data.error || `Error HTTP ${response.status}`, response.status)
    if (data.error) throw new ApiError(data.error, response.status)
    finishTrace(traceResponseOutcome(data),response.status)
    return data
  } catch (error) {
    finishTrace(signal?.aborted?'cancelled':timedOut?'timeout':error.status?'error':'network',error.status||0)
    if (signal?.aborted) throw new DOMException('Solicitud cancelada', 'AbortError')
    if (timedOut) throw new ApiError('La operación tardó demasiado. Reintenta; se conservará el mismo folio de operación.')
    if (error instanceof ApiError || error.name === 'AbortError') throw error
    throw new ApiError('No se pudo conectar con la API. Comprueba que esté encendida.')
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', cancel)
  }
}
