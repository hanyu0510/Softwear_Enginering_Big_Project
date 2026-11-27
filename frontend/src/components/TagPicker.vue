<script setup>
defineProps({ label: String, entries: { type: Array, default: () => [] } })
const model = defineModel({ type: Array, default: () => [] })
function toggle(value) {
  model.value = model.value.includes(value) ? model.value.filter(item => item !== value) : [...model.value, value]
}
</script>
<template>
  <fieldset class="picker-field">
    <legend class="field-label">{{ label }} <span class="meta">可多选</span></legend>
    <div class="choice-wrap">
      <button v-for="entry in entries" :key="entry.value" type="button" class="choice" :aria-pressed="model.includes(entry.value)" @click="toggle(entry.value)"><span>{{ entry.label }}</span></button>
    </div>
  </fieldset>
</template>
