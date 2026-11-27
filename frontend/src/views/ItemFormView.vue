<script setup>
import { computed, onScopeDispose, reactive, ref, shallowRef } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { api, loadIdentity, session } from '../api/session'
import { describeError } from '../api/http'
import { courseEnabled } from '../api/capabilities'
import { itemPath, prepareImage } from '../api/wardrobe'
import { useRequest } from '../composables/useRequest'
import { notify } from '../composables/useFeedback'
import AppButton from '../components/AppButton.vue'
import AppImage from '../components/AppImage.vue'
import AppIcon from '../components/AppIcon.vue'
import AppSheet from '../components/AppSheet.vue'
import StatusPanel from '../components/StatusPanel.vue'
import TagPicker from '../components/TagPicker.vue'

const route = useRoute()
const router = useRouter()
const id = route.params.id
const recognition = route.path.startsWith('/wardrobe/recognition/')
const newItem = !id
const stage = ref(newItem ? 'upload' : 'fields')
const preview = ref('')
const selected = shallowRef()
const uploaded = shallowRef()
const original = shallowRef()
const colorText = computed(() => !session.dictionary?.colors?.length)
const fields = reactive({ name: '', category: '', color: '', warmth: '', visibility: '', season: [], style: [], occasion: [] })
const busy = ref(false)
const action = ref('')
const message = ref('')
const badName = ref(false)
const badCategory = ref(false)
const recognizeFailed = ref(false)
const fieldChanged = ref(false)
const ask = ref(false)
let resolveNavigation
let active = true
const { busy: loading, error: loadError, run: requestItem } = useRequest(signal => api(itemPath(id), { signal }))
const title = computed(() => recognition ? '确认识图建议' : newItem ? '添加衣物' : '编辑衣物')

function setFields(item = {}) {
  for (const key of Object.keys(fields)) fields[key] = item[key] ?? (Array.isArray(fields[key]) ? [] : '')
  fields.visibility ||= 'private'
}
async function load() {
  const item = await requestItem()
  if (item) { original.value = item; setFields(item) }
}
if (id) load()
else setFields()

function releasePreview() {
  if (preview.value) URL.revokeObjectURL(preview.value)
  preview.value = ''
}
onScopeDispose(() => { active = false; releasePreview(); resolveNavigation?.(false) })
onBeforeRouteLeave(() => {
  if (!fieldChanged.value || !session.token || session.expired) return true
  ask.value = true
  return new Promise(resolve => { resolveNavigation = resolve })
})
function confirmLeave(allow) {
  if (allow) fieldChanged.value = false
  resolveNavigation?.(allow)
  resolveNavigation = undefined
  ask.value = false
}

async function choose(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || busy.value) return
  message.value = ''
  recognizeFailed.value = false
  busy.value = true
  action.value = 'preparing'
  try {
    const image = await prepareImage(file)
    if (!active) return
    releasePreview()
    selected.value = image
    uploaded.value = null
    preview.value = URL.createObjectURL(image)
  } catch (error) { message.value = describeError(error) }
  finally { busy.value = false; action.value = '' }
}
async function upload() {
  if (uploaded.value) return uploaded.value
  if (!selected.value) throw new Error('请选择衣物照片')
  const body = new FormData()
  body.append('file', selected.value)
  uploaded.value = await api('/uploads/image', { method: 'POST', body })
  return uploaded.value
}

async function analyze() {
  if (!courseEnabled || busy.value) return
  busy.value = true
  message.value = ''
  action.value = 'recognize'
  try {
    const { fileId } = await upload()
    const result = await api('/ai/recognize', { method: 'POST', body: { imageFileId: fileId } })
    if (active) await router.push('/wardrobe/recognition/' + result.id)
  } catch (error) {
    if (active && error.kind !== 'stale') {
      message.value = describeError(error)
      recognizeFailed.value = error.code === 50002
    }
  } finally { busy.value = false; action.value = '' }
}

async function save() {
  if (busy.value || !session.dictionary) return
  badName.value = !fields.name.trim()
  badCategory.value = !fields.category
  if (badName.value || badCategory.value) {
    document.getElementById(badName.value ? 'item-name' : 'item-category')?.focus()
    return
  }
  busy.value = true
  action.value = 'save'
  message.value = ''
  try {
    const values = { ...fields, name: fields.name.trim(), color: fields.color.trim() || null, warmth: fields.warmth === '' ? null : Number(fields.warmth) }
    let result
    if (newItem) {
      const { fileId } = await upload()
      result = await api('/items', { method: 'POST', body: { ...values, imageFileId: fileId } })
    } else {
      const changes = Object.fromEntries(Object.entries(values).filter(([key,value]) => JSON.stringify(original.value[key] ?? null) !== JSON.stringify(value)))
      result = Object.keys(changes).length ? await api(itemPath(id), { method: 'PATCH', body: changes }) : original.value
      if (recognition) result = await api(itemPath(id) + '/confirm', { method: 'POST' })
    }
    if (active) {
      fieldChanged.value = false
      notify(recognition ? '已确认并保存衣物' : '衣物已保存')
      await router.replace('/wardrobe/items/' + result.id)
    }
  } catch (error) { if (error.kind !== 'stale') message.value = describeError(error) }
  finally { busy.value = false; action.value = '' }
}
</script>

<template>
  <section class="screen screen-form item-form-screen">
    <div class="page-lead"><h1 class="display">{{ title }}</h1>
      <p v-if="newItem" class="body-small muted">{{ stage === 'upload' ? '先选一张清晰的衣物照片。' : '填写衣物信息并保存至个人衣橱。' }}</p>
    </div>
    <StatusPanel v-if="loading" loading />
    <StatusPanel v-else-if="loadError" error retry :message="loadError" @retry="load" />
    <template v-else>
      <p v-if="recognition && original" class="notice is-warning">
        <AppIcon name="info" /><span>识图流程演示 · 模拟建议。当前状态为待确认，请核对属性后保存。<template v-if="original.low_confidence_fields?.length"> 需核对 {{ original.low_confidence_fields.map(key => ({category:'分类',color:'颜色',warmth:'保暖度',season:'季节',style:'风格',occasion:'场合',material:'材质',pattern:'图案'})[key] || key).join('、') }}。</template></span>
      </p>
      <div class="item-form-layout">
      <div v-if="newItem" class="upload-block item-form-media">
        <AppImage v-if="preview" class="upload-preview" :preview="preview" alt="衣物预览" />
        <input id="garment-photo" type="file" class="file-input" accept="image/jpeg,image/png,image/webp" :disabled="busy" @change="choose">
        <label for="garment-photo" :class="preview ? 'button secondary' : 'upload-drop'">
          <span v-if="preview">重新选择图片</span><span v-else><AppIcon name="image" /><strong>选择衣物图片</strong><br><small class="meta">JPEG / PNG / WebP · 大图自动压缩</small></span>
        </label>
        <p v-if="action === 'preparing'" class="body-small muted" role="status">正在处理照片</p>
      </div>
      <AppImage v-else-if="original" class="upload-preview item-form-media" :path="original.image_url || original.thumb_url" :alt="original.name" eager />
      <div class="item-form-fields">
      <p v-if="message" class="notice is-error section" role="alert">{{ recognizeFailed ? '识图失败，可继续手动录入。' : '' }} {{ message }}</p>
      <section v-if="newItem && stage === 'upload'" class="section">
        <h2 class="section-title">选择录入方式</h2>
        <div class="upload-choices">
          <AppButton variant="secondary" :disabled="!selected || busy" @click="stage = 'fields'; message = ''"><AppIcon name="edit" /><span><strong>手动填写</strong><small>自选分类和属性</small></span></AppButton>
          <AppButton :disabled="!selected || !courseEnabled || busy && action !== 'recognize'" :busy="action === 'recognize'" @click="analyze"><AppIcon name="sparkle" /><span><strong>{{ action === 'recognize' ? '识别中' : 'AI 识图' }}</strong><small>{{ courseEnabled ? '识图流程演示 · 模拟建议' : '识图服务待接入' }}</small></span></AppButton>
        </div>
      </section>
      <StatusPanel v-else-if="!session.dictionary" retry title="衣物字典暂不可用" :message="session.detailsError" @retry="loadIdentity" />
      <form v-else class="stack section border-section" novalidate @submit.prevent="save" @input="fieldChanged = true" @change="fieldChanged = true">
        <div class="field"><label for="item-name">衣物名称</label><input id="item-name" v-model="fields.name" class="control" maxlength="120" required :aria-invalid="badName" aria-describedby="item-name-error" @input="badName = false"><p v-if="badName" id="item-name-error" class="form-error">请输入衣物名称</p></div>
        <div class="fields-pair">
          <div class="field"><label for="item-category">分类</label><select id="item-category" v-model="fields.category" class="control" required :aria-invalid="badCategory" aria-describedby="item-category-error" @change="badCategory = false"><option value="">选择分类</option><option v-for="entry in session.dictionary.categories" :key="entry.value" :value="entry.value">{{ entry.label }}</option></select><p v-if="badCategory" id="item-category-error" class="form-error">请选择分类</p></div>
          <div class="field"><label for="item-color">衣物颜色</label><input v-if="colorText" id="item-color" v-model="fields.color" class="control" maxlength="32" placeholder="可选，输入颜色文字"><select v-else id="item-color" v-model="fields.color" class="control"><option value="">未设置</option><option v-for="entry in session.dictionary.colors" :key="entry.value" :value="entry.value">{{ entry.label }}</option></select></div>
          <div class="field"><label for="item-warmth">保暖度</label><select id="item-warmth" v-model="fields.warmth" class="control"><option value="">未设置</option><option v-for="entry in session.dictionary.warmthLevels" :key="entry.value" :value="entry.value">{{ entry.label }}</option></select></div>
          <div class="field"><label for="item-visibility">可见性</label><select id="item-visibility" v-model="fields.visibility" class="control"><option v-for="entry in session.dictionary.visibilities" :key="entry.value" :value="entry.value">{{ entry.label }}</option></select></div>
        </div>
        <TagPicker v-model="fields.season" label="季节" :entries="session.dictionary.seasons" @update:model-value="fieldChanged = true" />
        <TagPicker v-model="fields.occasion" label="场合" :entries="session.dictionary.occasions" @update:model-value="fieldChanged = true" />
        <TagPicker v-model="fields.style" label="风格" :entries="session.dictionary.styles" @update:model-value="fieldChanged = true" />
        <AppButton type="submit" class="full" :busy="action === 'save'" :disabled="busy">{{ recognition ? '确认并保存' : newItem ? '保存到衣橱' : '保存修改' }}</AppButton>
      </form>
      </div>
      </div>
    </template>
    <AppSheet :model-value="ask" title="放弃未保存的修改？" @update:model-value="value => { if (!value) confirmLeave(false) }">
      <div class="actions"><AppButton variant="secondary" @click="confirmLeave(false)">继续编辑</AppButton><AppButton @click="confirmLeave(true)">放弃修改</AppButton></div>
    </AppSheet>
  </section>
</template>
