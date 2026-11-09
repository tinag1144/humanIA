export type Contract = {
  id: string
  estado: string
  datos: Record<string, unknown>
  aprobado_por?: string | null
  confirmado_por?: string | null
}
export type Draft = {
  id: number
  contrato_id: string
  version: number
  archivo: string
  fecha_generacion: string
  decision: string | null
  integridad?: boolean
}
export type ChatResult = { mensaje: string; sesion_id: string; herramientas: string[] }

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

function getError(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>
    if (typeof d.mensaje === 'string') return d.mensaje
    if (typeof d.detail === 'string') return d.detail
  }
  return fallback
}

export async function request<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      cache: 'no-store',
      headers: {
        ...(init.body && !(init.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers || {})
      }
    })
  } catch {
    throw new ApiError('No se pudo conectar con FastAPI. Comprobá que esté activo en el puerto 8001.', 0)
  }
  let body: unknown
  try { body = await response.json() } catch { body = null }
  if (!response.ok) {
    const d = body as { detail?: unknown; mensaje?: unknown } | null
    throw new ApiError(getError(d?.detail ?? d?.mensaje, `Error HTTP ${response.status}`), response.status)
  }
  return body as T
}

export async function login(usuario: string, clave: string): Promise<string> {
  const response = await request<Record<string, unknown>>('/api/login', null, {
    method: 'POST', body: JSON.stringify({ usuario, clave })
  })
  const nested = response.datos as Record<string, unknown> | undefined
  const token = response.token ?? response.access_token ?? nested?.token ?? nested?.access_token
  if (typeof token !== 'string' || token.length < 8) {
    throw new ApiError('El login no devolvió un token reconocido. Revisá la respuesta de /api/login.', 500)
  }
  return token
}

export async function download(path: string, token: string): Promise<void> {
  let response: Response
  try {
    response = await fetch(path, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' })
  } catch {
    throw new ApiError('No se pudo conectar con el servidor.', 0)
  }
  if (!response.ok) {
    let detail: unknown = null
    try { detail = (await response.json()).detail } catch { /* empty */ }
    throw new ApiError(getError(detail, `Error al descargar (${response.status})`), response.status)
  }
  const blob = await response.blob()
  const match = response.headers.get('Content-Disposition')?.match(/filename="?([^";]+)"?/i)
  const fallback = path.includes('constancia') ? 'constancia.pdf' : path.includes('pdf') ? 'contrato.pdf' : 'contrato.docx'
  const filename = match?.[1] || fallback
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1200)
}
