<script setup>
import { onScopeDispose, ref, watch } from 'vue'
import { api, session } from '../api/session'
import { localImage } from '../api/capabilities'
import AppIcon from './AppIcon.vue'

const props = defineProps({ path: String, preview: String, alt: { type: String, default: '' }, eager: Boolean })
const source = ref('')
const missing = ref(false)
let url = ''
let controller

function release() {
  controller?.abort()
  if (url) URL.revokeObjectURL(url)
  url = ''
}
watch(() => [props.path, props.preview, session.viewerVersion], async ([path, preview]) => {
  release()
  source.value = ''
  missing.value = false
  if (preview?.startsWith('blob:')) { source.value = preview; return }
  const safe = localImage(path)
  if (!safe) { missing.value = true; return }
  if (!safe.startsWith('/api/v1/uploads/')) {
    if (safe.startsWith('/api/')) missing.value = true
    else source.value = safe
    return
  }
  const request = new AbortController()
  controller = request
  try {
    const blob = await api(safe.slice('/api/v1'.length), { binary: true, signal: request.signal })
    if (request.signal.aborted) return
    url = URL.createObjectURL(blob)
    source.value = url
  } catch (error) {
    if (!request.signal.aborted && error.kind !== 'stale') missing.value = true
  }
}, { immediate: true })
onScopeDispose(release)
</script>

<template>
  <div class="image-frame" :aria-busy="!source && !missing || undefined">
    <span v-if="missing" class="image-placeholder"><AppIcon name="image" /><span v-if="alt">图片暂不可用</span></span>
    <img v-else-if="source" :src="source" :alt="alt" :loading="eager ? 'eager' : 'lazy'" decoding="async" @error="missing = true">
    <span v-else class="image-placeholder"><span class="spinner" aria-hidden="true" /><span class="visually-hidden">图片加载中</span></span>
  </div>
</template>
