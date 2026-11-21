<script setup>
import { useRoute, useRouter } from 'vue-router'
import { tabs } from './router/index.js'

const route = useRoute()
const router = useRouter()

function switchTab(path) {
  router.push(path)
}
</script>

<template>
  <main :class="{ page: route.meta.showTabBar }">
    <RouterView />
  </main>

  <t-tab-bar
    v-if="route.meta.showTabBar"
    :value="route.path"
    placeholder
    @change="switchTab"
  >
    <t-tab-bar-item
      v-for="tab in tabs"
      :key="tab.path"
      :value="tab.path"
    >
      {{ tab.label }}
    </t-tab-bar-item>
  </t-tab-bar>
</template>

<style>
:root {
  --td-tab-bar-active-color: #ec7057;
}

body {
  margin: 0;
  background: #faf7f2;
  color: #252522;
  font-family: system-ui, sans-serif;
}

.page {
  padding: 20px;
}
</style>
