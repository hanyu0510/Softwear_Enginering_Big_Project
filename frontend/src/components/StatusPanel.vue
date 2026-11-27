<script setup>
import AppButton from './AppButton.vue'
import AppIcon from './AppIcon.vue'
defineProps({ title: String, message: String, loading: Boolean, retry: Boolean, error: Boolean })
defineEmits(['retry'])
</script>
<template>
  <section class="status-panel" :role="error ? 'alert' : 'status'" :aria-busy="loading || undefined">
    <span v-if="loading" class="spinner" aria-hidden="true" />
    <AppIcon v-else :name="error ? 'refresh' : 'info'" />
    <h2 class="section-title">{{ title || (loading ? '正在加载' : '暂不可用') }}</h2>
    <p v-if="message" class="body-small muted wrap">{{ message }}</p>
    <AppButton v-if="retry" variant="secondary" @click="$emit('retry')">重试</AppButton>
    <slot />
  </section>
</template>
