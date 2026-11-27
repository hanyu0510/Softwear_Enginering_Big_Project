<script setup>
import { Button as TButton } from 'tdesign-mobile-vue'
defineProps({ variant: { type: String, default: 'primary' }, busy: Boolean, disabled: Boolean, type: { type: String, default: 'button' } })
</script>
<template>
  <t-button :class="['button', variant, 'brand-button']" :type="type" :loading="busy" :disabled="disabled || busy" :aria-busy="busy || undefined">
    <slot />
  </t-button>
</template>
