<script setup>
import { useRoute } from 'vue-router'
import { session } from '../api/session'
import AppIcon from './AppIcon.vue'
import AppImage from './AppImage.vue'
import BrandLink from './BrandLink.vue'
defineProps({ tabs: { type: Array, required: true } })

const route = useRoute()
function selected(path) {
  return route.path === path || route.path.startsWith(path + '/') || path === '/home' && route.path.startsWith('/posts/') && route.path !== '/posts/new'
}
</script>

<template>
  <aside class="desktop-sidebar">
    <BrandLink to="/home" />
    <nav class="desktop-navigation" aria-label="桌面主要导航">
      <RouterLink v-for="tab in tabs" :key="tab.path" :to="tab.path" :class="{ selected: selected(tab.path) }" :aria-current="selected(tab.path) ? 'page' : undefined">
        <AppIcon :name="tab.icon" /><span>{{ tab.desktopLabel || tab.label }}</span>
      </RouterLink>
    </nav>
    <RouterLink to="/posts/new" class="button primary publish-desktop"><AppIcon name="plus" />发布穿搭</RouterLink>
    <RouterLink v-if="session.user" to="/profile/account" class="sidebar-account">
      <AppImage v-if="session.user.avatar_url" class="avatar medium" :path="session.user.avatar_url" />
      <span v-else class="avatar-default"><AppIcon name="user" /></span>
      <span class="sidebar-account-label"><strong>{{ session.user.nickname }}</strong><small>账号管理</small></span>
    </RouterLink>
  </aside>
</template>
