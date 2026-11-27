<script setup>
import { icons } from '../icons'
defineProps({ name: { type: String, required: true } })
</script>
<template>
  <svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false" v-html="icons[name]" />
</template>
