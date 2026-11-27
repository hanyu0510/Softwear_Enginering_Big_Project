<script setup>
import { computed, onMounted, onScopeDispose, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/session'
import { query } from '../api/http'
import { courseEnabled } from '../api/capabilities'
import { useRequest } from '../composables/useRequest'
import AppButton from '../components/AppButton.vue'
import AppIcon from '../components/AppIcon.vue'
import AppSheet from '../components/AppSheet.vue'
import StatusPanel from '../components/StatusPanel.vue'
import PostCard from '../components/PostCard.vue'

const route = useRoute()
const router = useRouter()
const sort = computed(() => route.query.sort === 'newest' ? 'newest' : 'hot')
const rows = ref([])
const page = ref(1)
const hasMore = ref(false)
const search = ref(false)
const searchTerm = ref('')
const feedArea = ref()
const columns = ref(2)
const layout = new ResizeObserver(([entry]) => {
  const width = entry.contentRect.width
  columns.value = innerWidth < 768 ? 2 : innerWidth < 1024 ? 3 : Math.max(3, Math.min(7, Math.floor((width + 20) / 240)))
})
onMounted(() => layout.observe(feedArea.value))
onScopeDispose(() => layout.disconnect())
const groups = computed(() => Array.from({length:columns.value}, (_,i) => rows.value.filter((_,index) => index % columns.value === i)))
const pageSize = innerWidth >= 1024 ? 8 : 4
const { busy, error, run } = useRequest((signal, offset, order) => api('/posts' + query({ page:offset, pageSize, sort:order }), { signal }))
async function load(reset = false) {
  if (!reset && (busy.value || !hasMore.value)) return
  const target = reset ? 1 : page.value + 1
  if (reset) { rows.value = []; hasMore.value = false }
  const result = await run(target, sort.value)
  if (!result) return
  page.value = target
  hasMore.value = result.hasMore
  rows.value = reset ? result.list : [...rows.value, ...result.list.filter(post => !rows.value.some(existing => existing.id === post.id))]
}
watch(sort, () => load(true), { immediate:true })
let start = null
function touchStart(event) { start = scrollY <= 1 ? event.touches[0]?.clientY : null }
function touchEnd(event) {
  if (start !== null && scrollY <= 1 && event.changedTouches[0]?.clientY - start > 80 && !busy.value) load(true)
  start = null
}
</script>

<template>
  <section class="screen home-screen" @touchstart.passive="touchStart" @touchend.passive="touchEnd">
    <form class="desktop-search" @submit.prevent="search = true">
      <label for="community-search" class="visually-hidden">搜索穿搭帖子</label>
      <AppIcon name="search" /><input id="community-search" v-model="searchTerm" type="search" placeholder="搜索穿搭帖子" autocomplete="off" />
      <AppButton type="submit" variant="secondary">搜索</AppButton>
    </form>
    <div class="home-lead"><div><p class="eyebrow">穿搭灵感</p><h1 class="display">发现日常风格</h1></div><p v-if="courseEnabled" class="body-small muted">课程样本帖子 · 评论、点赞和收藏实时保存</p></div>
    <div class="feed-toolbar">
      <div class="underline-nav" aria-label="信息流排序"><button type="button" :aria-pressed="sort === 'hot'" @click="router.replace('/home')">推荐</button><button type="button" :aria-pressed="sort === 'newest'" @click="router.replace({path:'/home',query:{sort:'newest'}})">最新</button></div>
      <div class="actions"><button type="button" class="icon-button mobile-feed-search" aria-label="搜索帖子" @click="search = true"><AppIcon name="search" /></button><button type="button" class="icon-button" aria-label="刷新信息流" :disabled="busy" @click="load(true)"><AppIcon name="refresh" /></button></div>
    </div>
    <div ref="feedArea" class="feed-area">
    <div v-if="busy && !rows.length" class="skeleton-grid" role="status" aria-label="正在读取信息流"><div class="skeleton" /><div class="skeleton" /></div>
    <StatusPanel v-else-if="error && !rows.length" error retry title="信息流加载失败" :message="error" @retry="load(true)" />
    <StatusPanel v-else-if="!rows.length" title="暂时没有帖子" message="新帖子将在这里出现。" />
    <template v-else>
      <div class="feed" :style="{ '--feed-columns': columns }">
        <div v-for="(group,index) in groups" :key="index" class="feed-column">
          <PostCard v-for="(post,i) in group" :key="post.id" :post="post" :eager="i === 0" @update="patch => Object.assign(post,patch)" />
        </div>
      </div>
      <div v-if="hasMore || error" class="feed-end"><p v-if="error" class="notice is-error" role="alert">{{ error }}</p><AppButton variant="secondary" :busy="busy" @click="load()">{{ error ? '重试加载' : '加载更多' }}</AppButton></div>
    </template>
    </div>
    <AppSheet v-model="search" title="搜索帖子"><p class="body-small muted">帖子搜索暂未接入，可以继续浏览推荐和最新内容。</p></AppSheet>
  </section>
</template>
