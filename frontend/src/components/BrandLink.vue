<script setup>
import mark from '../assets/yida-mark.svg'
defineProps({ to: { type: String, required: true } })
</script>

<template>
  <RouterLink :to="to" class="brand" aria-label="衣搭 YIDA">
    <img :src="mark" alt="" class="mark"><span class="brand-word" lang="en">YIDA</span><span class="brand-zh">衣搭</span>
  </RouterLink>
</template>
