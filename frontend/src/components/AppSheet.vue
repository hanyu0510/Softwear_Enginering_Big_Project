<script setup>
import { ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'
defineProps({ title: { type: String, required: true } })
const open = defineModel({ type: Boolean, default: false })
const element = ref()
let opener
watch(open, (value) => {
  if (value && element.value && !element.value.open) {
    opener = document.activeElement
    element.value.showModal()
  } else if (!value && element.value?.open) element.value.close()
}, { flush: 'post' })

function closed() {
  open.value = false
  if (opener?.isConnected) opener.focus({ preventScroll: true })
}
</script>
<template>
  <dialog ref="element" class="sheet" :aria-label="title" @close="closed" @click.self="open = false">
    <div class="sheet-inner">
      <header class="sheet-header"><h2 class="section-title">{{ title }}</h2><button type="button" class="icon-button" aria-label="关闭面板" @click="open = false"><AppIcon name="close" /></button></header>
      <div class="sheet-content"><slot /></div>
    </div>
  </dialog>
</template>
