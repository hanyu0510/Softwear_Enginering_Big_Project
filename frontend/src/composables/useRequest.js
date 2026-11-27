import { onScopeDispose, ref, shallowRef } from 'vue'
import { describeError } from '../api/http'

export function useRequest(fetcher) {
  const data = shallowRef(null)
  const error = ref('')
  const busy = ref(false)
  let controller

  async function run(...args) {
    controller?.abort()
    const request = new AbortController()
    controller = request
    busy.value = true
    error.value = ''
    try {
      const result = await fetcher(request.signal, ...args)
      if (!request.signal.aborted) { data.value = result; return result }
    } catch (problem) {
      if (!request.signal.aborted && problem.kind !== 'stale') error.value = describeError(problem)
    } finally {
      if (controller === request) busy.value = false
    }
    return undefined
  }
  function cancel() {
    controller?.abort()
    controller = null
    busy.value = false
    error.value = ''
    data.value = null
  }
  onScopeDispose(cancel)
  return { data, error, busy, run, cancel }
}
