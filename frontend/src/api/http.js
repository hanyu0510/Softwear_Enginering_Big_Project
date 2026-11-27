export class ApiError extends Error {
  constructor(kind, message, details = {}) {
    super(message)
    this.kind = kind
    this.status = details.status
    this.code = details.code
    this.requestId = details.requestId
  }
}

export const invalidSession = error => error?.code === 40101 && error.status === 401
export const stale = () => new ApiError('stale', '会话或页面已切换')
export const describeError = error => error?.requestId ? `${error.message}（请求编号 ${error.requestId}）` : error?.message || '请求暂未完成'

export async function send(url, { method = 'GET', body, token, signal, binary = false, credentials = 'include' } = {}) {
  const headers = new Headers({ Accept: binary ? 'image/*' : 'application/json' })
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let payload = body
  if (body !== undefined && !(body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
    payload = JSON.stringify(body)
  }
  let response
  try {
    response = await fetch(url, { method, headers, body: payload, credentials, signal, cache: 'no-store', redirect: 'error' })
  } catch (error) {
    if (signal?.aborted) throw stale()
    throw new ApiError('network', '连接暂时不可用，请检查服务后重试')
  }
  const type = response.headers.get('content-type') || ''
  if (binary && response.ok && type.startsWith('image/')) return response.blob()
  const data = type.includes('application/json') ? await response.json().catch(() => null) : null
  if (response.ok && data?.code === 0 && !binary) return data.data
  const status = response.status
  throw new ApiError(response.ok ? (data ? 'business' : 'protocol') : 'http',
    data?.message || (status >= 500 ? '服务暂时不可用，请重试' : binary && response.ok ? '图片响应格式不正确' : `请求未完成（HTTP ${status}）`),
    { status, code: data?.code, requestId: data?.requestId || response.headers.get('x-request-id') })
}

export function query(filters) {
  const params = new URLSearchParams(Object.entries(filters).filter(([,value]) => value !== '' && value != null))
  const suffix = params.toString()
  return suffix ? `?${suffix}` : ''
}
