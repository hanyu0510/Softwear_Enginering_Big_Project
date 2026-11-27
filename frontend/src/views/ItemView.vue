<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/session'
import { describeError } from '../api/http'
import { itemPath, labelFor } from '../api/wardrobe'
import { useRequest } from '../composables/useRequest'
import AppImage from '../components/AppImage.vue'
import AppIcon from '../components/AppIcon.vue'
import StatusPanel from '../components/StatusPanel.vue'

const id = useRoute().params.id
const { data: item, busy, error, run } = useRequest(signal => api(itemPath(id), { signal }))
const pending = ref(false)
const actionError = ref('')
run()

const rows = computed(() => {
  const i = item.value
  const list = (key,values) => values.map(value => labelFor(key,value)).join('、') || '未设置'
  return [['分类',labelFor('categories',i.category)],['颜色',i.color],['季节',list('seasons',i.season)],['场合',list('occasions',i.occasion)],['风格',list('styles',i.style)],['保暖度',labelFor('warmthLevels',i.warmth)],['可见性',labelFor('visibilities',i.visibility)]]
})
async function favorite() {
  pending.value = true
  actionError.value = ''
  try { item.value = await api(itemPath(id), { method:'PATCH', body:{is_favorite:!item.value.is_favorite} }) }
  catch (problem) { if (problem.kind !== 'stale') actionError.value = describeError(problem) }
  finally { pending.value = false }
}
</script>
<template>
  <section v-if="busy || error" class="screen screen-form">
    <StatusPanel v-if="busy" loading title="正在读取衣物" />
    <StatusPanel v-else error retry title="无法读取衣物" :message="error" @retry="run" />
  </section>
  <article v-else-if="item" class="screen item-detail-layout">
    <AppImage class="item-detail-photo" :path="item.image_url" :alt="item.name" eager />
    <div><div class="page-lead"><h1 class="display">{{ item.name }}</h1><p class="tag" :class="item.verify_status === 'confirmed' ? 'success' : 'warning'">{{ labelFor('verifyStatuses',item.verify_status) }}</p></div>
      <dl class="attributes"><div v-for="[label,value] in rows" :key="label"><dt>{{ label }}</dt><dd>{{ value || '未设置' }}</dd></div></dl>
      <div class="actions">
        <RouterLink v-if="item.verify_status === 'pending'" class="button primary" :to="'/wardrobe/recognition/' + id">确认识图建议</RouterLink>
        <RouterLink v-else :to="'/wardrobe/items/' + id + '/edit'" class="button primary"><AppIcon name="edit" />编辑衣物</RouterLink>
        <button class="icon-button" type="button" :disabled="pending" :aria-pressed="item.is_favorite" :aria-label="item.is_favorite ? '取消收藏衣物' : '收藏衣物'" @click="favorite"><AppIcon name="heart" /></button>
      </div>
      <p v-if="actionError" class="notice is-error section" role="alert">{{ actionError }}</p>
    </div>
  </article>
</template>
