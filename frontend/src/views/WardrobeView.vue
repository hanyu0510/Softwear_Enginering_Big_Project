<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, loadIdentity, session } from '../api/session'
import { query } from '../api/http'
import { labelFor } from '../api/wardrobe'
import { useRequest } from '../composables/useRequest'
import AppIcon from '../components/AppIcon.vue'
import AppButton from '../components/AppButton.vue'
import AppImage from '../components/AppImage.vue'
import AppSheet from '../components/AppSheet.vue'
import StatusPanel from '../components/StatusPanel.vue'

const route = useRoute()
const router = useRouter()
const filters = computed(() => Object.fromEntries(['category','keyword','season','color'].map(key => [key,String(route.query[key] || '')])))
const page = computed(() => Math.max(1, Number(route.query.page) || 1))
const pageSize = 8
const text = ref('')
const showFilters = ref(false)
const showWish = ref(false)
const draft = reactive({ season: '', color: '' })
const { data, error, busy, run } = useRequest((signal, options) => api('/items' + query(options), { signal }))
const { data: inventory, run: totalCount } = useRequest(signal => api('/items?page=1&pageSize=1', { signal }))
totalCount()
watch(() => route.query, () => {
  if (route.path !== '/wardrobe') return
  text.value = filters.value.keyword
  run({ ...filters.value, page: page.value, pageSize })
}, { immediate: true })

function update(patch) {
  const entries = Object.entries({ ...filters.value, ...patch }).filter(([,value]) => value !== '')
  router.replace({ path: '/wardrobe', query: Object.fromEntries(entries) })
}
function openFilters() {
  Object.assign(draft, { season: filters.value.season, color: filters.value.color })
  showFilters.value = true
}
function applyFilters() {
  update({ ...draft, color: draft.color.trim() })
  showFilters.value = false
}
const retry = () => { totalCount(); run({ ...filters.value, page: page.value, pageSize }) }
</script>

<template>
  <section class="screen wardrobe-screen">
    <header class="wardrobe-banner compact-banner">
      <div><h1 class="display">我的衣橱</h1><p class="body-small muted" v-if="inventory">{{ inventory.total }} 件衣物</p></div>
      <RouterLink to="/wardrobe/new" class="button primary"><AppIcon name="plus" />添加衣物</RouterLink>
    </header>
    <div class="wardrobe-controls">
      <div v-if="session.dictionary" class="underline-nav" aria-label="衣物分类">
        <button v-for="entry in [{value:'', label:'全部'}, ...session.dictionary.categories]" :key="entry.value" type="button"
          :aria-pressed="filters.category === entry.value" @click="update({category:entry.value})">{{ entry.label }}</button>
      </div>
      <p v-else-if="session.detailsError" class="notice is-error" role="alert">{{ session.detailsError }} <button class="text-button" @click="loadIdentity">重试字典</button></p>
      <form class="search-row wardrobe-search" @submit.prevent="update({keyword:text.trim()})">
        <label class="visually-hidden" for="wardrobe-search">搜索衣物</label>
        <input id="wardrobe-search" v-model="text" class="control" type="search" placeholder="搜索名称或颜色" maxlength="120">
        <AppButton type="submit" variant="secondary">搜索</AppButton>
        <AppButton variant="secondary" @click="openFilters"><AppIcon name="filter" />筛选{{ filters.season || filters.color ? ' · 已选' : '' }}</AppButton>
      </form>
    </div>
    <StatusPanel v-if="busy" loading title="正在读取衣橱" />
    <StatusPanel v-else-if="error" error retry title="衣橱加载失败" :message="error" @retry="retry" />
    <template v-else-if="data?.list.length">
      <div class="wardrobe-grid">
        <article v-for="item in data.list" :key="item.id" class="item-card">
          <RouterLink :to="'/wardrobe/items/' + item.id">
            <AppImage class="item-image" :path="item.thumb_url" :alt="item.name" />
            <div class="item-card-copy"><h2>{{ item.name }}</h2><p class="meta">{{ labelFor('categories', item.category) }}</p><span v-if="item.verify_status !== 'confirmed'" class="tag warning">{{ labelFor('verifyStatuses', item.verify_status) }}</span></div>
          </RouterLink>
        </article>
      </div>
      <div v-if="data.total > pageSize || page > 1" class="spread section" aria-label="衣橱分页">
        <AppButton variant="secondary" :disabled="page <= 1" @click="update({page:page-1})">上一页</AppButton>
        <span class="meta">第 {{ page }} 页 · 共 {{ data.total }} 件</span>
        <AppButton variant="secondary" :disabled="page * pageSize >= data.total" @click="update({page:page+1})">下一页</AppButton>
      </div>
    </template>
    <StatusPanel v-else title="暂时没有符合条件的衣物" message="可以调整筛选，或添加一件衣物。">
      <AppButton variant="secondary" @click="update({category:'',keyword:'',season:'',color:''})">清除筛选</AppButton>
    </StatusPanel>
    <div class="wardrobe-footer spread"><h2 class="section-title">心愿衣橱</h2><AppButton variant="quiet" @click="showWish = true">查看状态</AppButton></div>
    <AppSheet v-model="showFilters" title="筛选衣物">
      <form class="stack" @submit.prevent="applyFilters">
        <div class="field"><label for="filter-season">季节</label><select id="filter-season" v-model="draft.season" class="control"><option value="">全部</option><option v-for="entry in session.dictionary?.seasons" :key="entry.value" :value="entry.value">{{ entry.label }}</option></select></div>
        <div class="field"><label for="filter-color">衣物颜色</label><input id="filter-color" v-model="draft.color" class="control" placeholder="输入衣物上的颜色文字" maxlength="32"></div>
        <AppButton type="submit" class="full">应用筛选</AppButton>
      </form>
    </AppSheet>
    <AppSheet v-model="showWish" title="心愿衣橱"><p class="body-small muted">课堂版本先提供个人衣物管理。心愿衣橱入口将在后续开放。</p></AppSheet>
  </section>
</template>
