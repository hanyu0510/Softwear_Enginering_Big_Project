<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, loadIdentity, session } from '../api/session'
import { describeError } from '../api/http'
import { labelFor } from '../api/wardrobe'
import { useRequest } from '../composables/useRequest'
import { notify } from '../composables/useFeedback'
import AppButton from '../components/AppButton.vue'
import StatusPanel from '../components/StatusPanel.vue'
import TagPicker from '../components/TagPicker.vue'

const section = useRoute().params.section
const headings = { posts:'我的帖子',likes:'我的点赞',favorites:'我的收藏',following:'关注',followers:'粉丝',notifications:'消息通知',preferences:'穿搭偏好' }
const paths = { posts:'/me/posts',likes:'/me/likes',favorites:'/me/favorites',following:'/me/following',followers:'/me/followers',notifications:'/notifications',preferences:'/me/style-preferences' }
const postList = ['posts','likes','favorites'].includes(section)
const allowed = computed(() => !!paths[section] && (!postList || session.config?.myPostListsEnabled === true))
const { data, error, busy, run } = useRequest(signal => api(paths[section],{signal}))
const form = reactive({styles:[],avoid_colors:[],notes:''})
const saving = ref(false)
const failure = ref('')
async function load() {
  const result = await run()
  if (result && section === 'preferences') Object.assign(form,result)
}

watch(allowed, value => { if (value) load() }, {immediate:true})

async function save() {
  saving.value = true
  failure.value = ''
  try {
    const payload = {...form, avoid_colors:session.config?.colorPreferencesEnabled ? form.avoid_colors : []}
    const result = await api(paths.preferences,{method:'PUT',body:payload})
    Object.assign(form,result)
    notify('穿搭偏好已保存')
  } catch (problem) { if (problem.kind !== 'stale') failure.value = describeError(problem) }
  finally { saving.value = false }
}
async function mark(id) {
  failure.value = ''
  try { await api('/notifications/' + encodeURIComponent(id) + '/read',{method:'PUT'}); await run() }
  catch (problem) { if (problem.kind !== 'stale') failure.value = describeError(problem) }
}
</script>
<template>
  <section class="screen screen-form"><div class="page-lead"><h1 class="display">{{ headings[section] || '个人记录' }}</h1></div>
    <StatusPanel v-if="!allowed" :title="postList && !session.config ? '功能状态待确认' : '暂未接入'"
      :message="postList && !session.config ? session.detailsError : section === 'favorites' ? '这里用于查看收藏的帖子，列表查询待接入。' : '此列表暂未开放。'"
      :retry="postList && !session.config" @retry="loadIdentity" />
    <StatusPanel v-else-if="busy" loading />
    <StatusPanel v-else-if="error" error retry :message="error" @retry="load" />
    <form v-else-if="section === 'preferences' && data" class="stack" @submit.prevent="save">
      <TagPicker v-model="form.styles" label="常穿风格" :entries="session.dictionary?.styles" />
      <TagPicker v-if="session.config?.colorPreferencesEnabled" v-model="form.avoid_colors" label="想避开的颜色" :entries="session.dictionary?.colors" />
      <p v-else class="notice">颜色偏好待统一字典接入。</p>
      <div class="field"><label for="preferences-notes">其他偏好</label><textarea id="preferences-notes" v-model="form.notes" class="control" maxlength="500" /></div>
      <AppButton type="submit" :busy="saving">保存偏好</AppButton>
    </form>
    <ul v-else-if="data?.list?.length" class="comment-list">
      <li v-for="row in data.list" :key="row.id">
        <RouterLink v-if="postList" class="text-button" :to="'/posts/' + row.id">{{ row.title }}</RouterLink>
        <template v-else-if="section === 'notifications'"><strong>{{ labelFor('notificationTypes',row.type) }}</strong><p>{{ row.from_user?.nickname }}</p><AppButton v-if="!row.is_read" variant="secondary" @click="mark(row.id)">标记已读</AppButton></template>
        <template v-else><strong>{{ row.nickname }}</strong></template>
      </li>
    </ul>
    <StatusPanel v-else title="暂无记录" />
    <p v-if="failure" class="notice is-error" role="alert">{{ failure }}</p>
  </section>
</template>
