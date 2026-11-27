<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { session } from './api/session'
import { feedback } from './composables/useFeedback'
import { tabs } from './router'
import AppIcon from './components/AppIcon.vue'
import BrandLink from './components/BrandLink.vue'
import DesktopSidebar from './components/DesktopSidebar.vue'
import StatusPanel from './components/StatusPanel.vue'

const router = useRouter()
const route = useRoute()
const main = ref()
const back = computed(() => typeof route.meta.back === 'function' ? route.meta.back(route) : route.meta.back)
watch(() => session.expired, expired => {
  if (expired && route.meta.private) router.replace({ path: '/login', query: { next: route.fullPath, expired: '1' } })
})
watch(() => route.path, async () => {
  await nextTick()
  main.value?.focus({ preventScroll: true })
}, { flush: 'post' })

function previous(event) {
  const prior = history.state?.back
  if (route.meta.returnScroll && (prior === back.value || prior?.startsWith(back.value + '?'))) {
    event.preventDefault()
    router.back()
  }
}
</script>

<template>
  <div :class="{ 'has-tabs': route.meta.showTabBar, 'app-shell': route.meta.private }">
    <a class="skip-link" href="#main-content" @click.prevent="main?.focus()">跳到主要内容</a>
    <DesktopSidebar v-if="route.meta.private && session.token" :tabs="tabs" />
    <header class="site-header" :class="{ 'shell-header': route.meta.private, 'root-header': route.meta.showTabBar }">
      <div v-if="back" class="header-inner section-header">
        <RouterLink :to="back" custom v-slot="{ href, navigate }"><a :href="href" class="icon-button back-link" aria-label="返回" @click="event => { previous(event); if (!event.defaultPrevented) navigate(event) }"><AppIcon name="back" /></a></RouterLink>
        <span class="subhead">{{ route.meta.title }}</span><span />
      </div>
      <div v-else class="header-inner">
        <BrandLink :to="session.token ? '/home' : '/login'" />
        <RouterLink v-if="route.path === '/home'" to="/posts/new" class="button primary publish-mobile"><AppIcon name="plus" />发布</RouterLink>
      </div>
    </header>
    <main id="main-content" ref="main" tabindex="-1">
      <div v-if="!session.ready" class="screen"><StatusPanel loading title="正在读取会话" /></div>
      <RouterView v-else :key="session.viewerVersion + ':' + route.path" />
    </main>
    <nav v-if="route.meta.showTabBar" class="tab-bar" aria-label="主要导航">
      <RouterLink v-for="tab in tabs" :key="tab.path" :to="tab.path" class="tab" :aria-current="route.path === tab.path ? 'page' : undefined">
        <AppIcon :name="tab.icon" /><span>{{ tab.label }}</span>
      </RouterLink>
    </nav>
    <div class="toast" role="status" aria-live="polite">{{ feedback }}</div>
  </div>
</template>
