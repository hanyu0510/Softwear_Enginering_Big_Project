<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { loadIdentity, logout, session } from '../api/session'
import { describeError } from '../api/http'
import AppButton from '../components/AppButton.vue'
import AppIcon from '../components/AppIcon.vue'
import AppImage from '../components/AppImage.vue'
import AppSheet from '../components/AppSheet.vue'
import StatusPanel from '../components/StatusPanel.vue'

const router = useRouter()
const ask = ref(false)
const busy = ref(false)
const message = ref('')
const shortcuts = [{ id:'posts',label:'我的帖子',icon:'grid' },{ id:'likes',label:'我的点赞',icon:'heart' },{ id:'favorites',label:'我的收藏',icon:'bookmark' }]
const menu = [{ id:'notifications',label:'消息通知',icon:'bell' },{ id:'preferences',label:'穿搭偏好',icon:'hanger' },{ id:'account',label:'账号管理',icon:'settings' }]
async function exit() {
  if (busy.value) return
  busy.value = true
  message.value = ''
  try { await logout(); ask.value = false; await router.replace('/login') }
  catch (error) { if (error.kind !== 'stale') message.value = describeError(error) }
  finally { busy.value = false }
}
</script>

<template>
  <section class="screen screen-form profile-screen">
    <div class="page-lead"><h1 class="display">我的</h1></div>
    <div class="profile-layout">
    <StatusPanel v-if="!session.user" class="profile-summary" title="暂未读取个人资料" retry :message="session.detailsError" @retry="loadIdentity" />
    <section v-else class="profile-card profile-summary" aria-label="个人资料">
      <div class="identity"><AppImage v-if="session.user.avatar_url" class="avatar large" :path="session.user.avatar_url" :alt="session.user.nickname" eager /><span v-else class="avatar-default"><AppIcon name="user" /></span>
        <div><h2 class="title">{{ session.user.nickname }}</h2><p class="body-small muted wrap">{{ session.user.email }}</p></div>
      </div>
      <div class="profile-stats">
        <RouterLink to="/profile/following" class="text-button"><strong>{{ session.user.following_count }}</strong>关注</RouterLink>
        <RouterLink to="/profile/followers" class="text-button"><strong>{{ session.user.follower_count }}</strong>粉丝</RouterLink>
      </div>
    </section>
    <div class="profile-tools">
    <section class="section"><h2 class="section-title">社区记录</h2><div class="profile-shortcuts">
      <RouterLink v-for="slot in shortcuts" :key="slot.id" class="shortcut" :to="'/profile/' + slot.id"><AppIcon :name="slot.icon" /><span>{{ slot.label }}</span><small v-if="!session.config?.myPostListsEnabled" class="meta">{{ session.config ? '待接入' : '状态待确认' }}</small></RouterLink>
    </div></section>
    <section class="section"><h2 class="section-title">个人设置</h2><div class="profile-menu">
      <RouterLink v-for="item in menu" :key="item.id" class="menu-row" :to="'/profile/' + item.id"><AppIcon :name="item.icon" /><span class="main-label">{{ item.label }}</span><AppIcon name="next" /></RouterLink>
    </div></section>
    <div class="profile-footer"><AppButton variant="secondary" class="full" @click="ask = true">退出登录</AppButton></div>
    </div>
    </div>
    <AppSheet v-model="ask" title="退出登录？">
      <p class="body-small muted">当前登录会话将结束。</p>
      <p v-if="message" class="notice is-error" role="alert">{{ message }}</p>
      <div class="actions"><AppButton variant="secondary" :disabled="busy" @click="ask = false">继续使用</AppButton><AppButton :busy="busy" @click="exit">退出</AppButton></div>
    </AppSheet>
  </section>
</template>
