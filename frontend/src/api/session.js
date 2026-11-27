import { reactive } from 'vue'
import { ApiError, describeError, invalidSession, send, stale } from './http'

const key = 'yida.access'
const prefix = '/api/v1'
export const session = reactive({
  token: sessionStorage.getItem(key) || '', user: null, dictionary: null, config: null,
  epoch: 0, viewerVersion: 0, ready: false, expired: false, message: '', detailsError: '',
})
let changePending = false
let refreshJob = null
let restoreJob = null
let detailsJob = null

function storeToken(token) {
  session.token = token
  if (token) sessionStorage.setItem(key, token)
  else sessionStorage.removeItem(key)
}

function clearIdentity() {
  session.viewerVersion++
  storeToken('')
  session.user = session.dictionary = session.config = null
  session.detailsError = ''
}

function checkEpoch(epoch, signal) {
  if (epoch !== session.epoch || signal?.aborted) throw stale()
}

function refresh(epoch) {
  checkEpoch(epoch)
  if (changePending) throw stale()
  if (refreshJob?.epoch === epoch) return refreshJob.promise
  const promise = send(`${prefix}/auth/refresh`, { method: 'POST' }).then(result => {
    checkEpoch(epoch)
    if (!result?.token) throw new ApiError('protocol', '会话响应缺少访问凭据')
    storeToken(result.token)
    return result.token
  }).catch(error => {
    if (epoch === session.epoch && invalidSession(error)) {
      session.epoch++
      clearIdentity()
      session.expired = true
    }
    throw error
  }).finally(() => { if (refreshJob?.promise === promise) refreshJob = null })
  refreshJob = { epoch, promise }
  return promise
}

export async function api(path, options = {}) {
  const epoch = session.epoch
  if (changePending) throw stale()
  const token = session.token
  let result
  try {
    result = await send(prefix + path, { ...options, token })
  } catch (error) {
    checkEpoch(epoch, options.signal)
    if (!token || !invalidSession(error) || path.startsWith('/auth/')) throw error
    if (session.token === token) await refresh(epoch)
    checkEpoch(epoch, options.signal)
    result = await send(prefix + path, { ...options, token: session.token })
  }
  checkEpoch(epoch, options.signal)
  return result
}

export function loadIdentity() {
  const epoch = session.epoch
  if (detailsJob?.epoch === epoch) return detailsJob.promise
  const fields = [['user', '/me'], ['dictionary', '/dict'], ['config', '/config']]
  const promise = Promise.allSettled(fields.map(([,path]) => api(path))).then(results => {
    if (epoch !== session.epoch) return
    const problems = []
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') session[fields[index][0]] = result.value
      else if (result.reason?.kind !== 'stale') problems.push(describeError(result.reason))
    })
    session.detailsError = [...new Set(problems)].join('；')
  }).finally(() => { if (detailsJob?.promise === promise) detailsJob = null })
  detailsJob = { epoch, promise }
  return promise
}

export function restoreSession() {
  if (session.ready) return Promise.resolve()
  if (restoreJob) return restoreJob
  restoreJob = (async () => {
    const epoch = session.epoch
    try {
      if (!session.token) await refresh(epoch)
      await loadIdentity()
    } catch (error) {
      if (epoch === session.epoch && error?.kind !== 'stale') session.message = describeError(error)
    } finally {
      session.expired = false
      session.ready = true
      restoreJob = null
    }
  })()
  return restoreJob
}

async function changeIdentity(path, body, { authenticate = false, sendsToken = false } = {}) {
  if (changePending) throw stale()
  changePending = true
  session.epoch++
  const token = session.token
  try {
    // Wait for a rotating response before another request can set or clear the same Cookie.
    if (refreshJob) await refreshJob.promise.catch(() => {})
    const result = await send(prefix + path, { method: 'POST', body, token: sendsToken ? token : undefined })
    clearIdentity()
    session.expired = false
    session.message = ''
    if (authenticate) {
      if (!result?.token || !result?.user) throw new ApiError('protocol', '登录响应缺少账户信息')
      storeToken(result.token)
      session.user = result.user
    }
    return result
  } finally {
    changePending = false
  }
}

export async function login(body) {
  await changeIdentity('/auth/login', body, { authenticate: true })
  await loadIdentity()
}

export const register = body => send(`${prefix}/auth/register`, { method: 'POST', body })
export const resetPassword = body => changeIdentity('/auth/forgot-password', body)
export async function changePassword(body) {
  await api('/me/change-password', { method: 'POST', body })
  session.epoch++
  clearIdentity()
  session.expired = false
  session.message = ''
}
export const logout = () => changeIdentity('/auth/logout', undefined, { sendsToken: true })
