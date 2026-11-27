<script setup>
import { computed, nextTick, onScopeDispose, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import AppButton from '../components/AppButton.vue'
import AppIcon from '../components/AppIcon.vue'
import AppSheet from '../components/AppSheet.vue'

const draft = reactive({ title: '', text: '', post_type: 'outfit', tags: '' })
const images = ref([])
const imageError = ref('')
const touched = reactive({ title: false, text: false, images: false })
const summary = ref()
const submitted = ref(false)
const checking = ref(false)
const asking = ref(false)
const formats = ['image/jpeg', 'image/png', 'image/webp']
const maxImageSize = 10 * 1024 * 1024
const previewLimit = 9
let resolveLeave
let disposed = false
let imageKey = 0

const dirty = computed(() => !!(draft.title || draft.text || draft.tags || draft.post_type !== 'outfit' || images.value.length || checking.value))
const errors = computed(() => ({
  images: touched.images && !images.value.length ? '请至少添加一张图片用于预览。' : '',
  title: touched.title && !draft.title.trim() ? '请填写标题。' : '',
  text: touched.text && !draft.text.trim() ? '请填写正文。' : '',
}))
const invalid = computed(() => Object.entries(errors.value).filter(([,message]) => message))
const tags = computed(() => [...new Set(draft.tags.split(/[,，、\n]/).map(tag => tag.trim()).filter(Boolean))])

async function selectImages(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (!files.length || checking.value) return
  checking.value = true
  const problems = []
  try {
    for (const file of files) {
      if (disposed) return
      if (images.value.length >= previewLimit) { problems.push(`编辑预览最多保留 ${previewLimit} 张照片。`); break }
      if (!formats.includes(file.type) || file.size > maxImageSize) { problems.push('请选择 10 MB 以内的 JPEG、PNG 或 WebP 图片。'); continue }
      const url = URL.createObjectURL(file)
      const preview = new Image()
      preview.src = url
      try {
        await preview.decode()
        if (disposed) URL.revokeObjectURL(url)
        else images.value.push({ id: ++imageKey, url, name: file.name })
      } catch {
        URL.revokeObjectURL(url)
        problems.push(`无法读取「${file.name}」。`)
      }
    }
    imageError.value = [...new Set(problems)].join(' ')
  } finally { checking.value = false }
}

function remove(index) {
  URL.revokeObjectURL(images.value[index].url)
  images.value.splice(index, 1)
}

function move(index, step) {
  const destination = index + step
  if (destination < 0 || destination >= images.value.length) return
  const [photo] = images.value.splice(index, 1)
  images.value.splice(destination, 0, photo)
}

function leave(answer) {
  const finish = resolveLeave
  resolveLeave = null
  asking.value = false
  finish?.(answer)
}

function confirmReload(event) {
  if (dirty.value) { event.preventDefault(); event.returnValue = '' }
}

onBeforeRouteLeave(to => {
  if (!dirty.value || to.path === '/login') return true
  resolveLeave?.(false)
  asking.value = true
  return new Promise(resolve => { resolveLeave = resolve })
})
window.addEventListener('beforeunload', confirmReload)
onScopeDispose(() => {
  disposed = true
  images.value.forEach(photo => URL.revokeObjectURL(photo.url))
  window.removeEventListener('beforeunload', confirmReload)
  resolveLeave?.(false)
})

async function validate() {
  submitted.value = true
  Object.assign(touched, { title: true, text: true, images: true })
  if (!invalid.value.length) return
  await nextTick()
  summary.value?.focus()
}

// Integrate POST /api/v1/posts here after media URLs and public associations are agreed and verified.
</script>

<template>
  <section class="screen compose-screen">
    <div class="page-lead"><h1 class="display">发布穿搭</h1></div>
    <p class="notice compose-status" id="compose-status"><AppIcon name="info" />发帖服务暂未接入，当前仅支持编辑预览。</p>
    <form class="compose-layout" novalidate @submit.prevent="validate">
      <section v-if="submitted && invalid.length" ref="summary" tabindex="-1" class="notice is-error compose-summary" aria-label="编辑预览待补充">
        <div><strong>请补充以下内容</strong><ul><li v-for="[field,message] in invalid" :key="field"><button class="text-button" type="button" @click="$el.querySelector('#compose-' + field)?.focus()">{{ message }}</button></li></ul></div>
      </section>
      <section class="compose-media" aria-labelledby="compose-media-title">
        <div class="spread"><h2 id="compose-media-title" class="section-title">穿搭照片</h2><p class="meta" aria-live="polite">已选 {{ images.length }} 张</p></div>
        <input id="compose-images" type="file" class="file-input" multiple accept="image/jpeg,image/png,image/webp" :disabled="checking" :aria-invalid="!!errors.images" :aria-describedby="imageError || errors.images ? 'compose-photo-hint compose-image-error' : 'compose-photo-hint'" @change="selectImages">
        <label for="compose-images" class="upload-drop compose-upload" :class="{ 'with-photos': images.length }">
          <span><AppIcon :name="images.length ? 'plus' : 'image'" /><strong>{{ checking ? '正在读取照片' : images.length ? '继续添加照片' : '选择穿搭照片' }}</strong><small id="compose-photo-hint">JPEG、PNG 或 WebP · 单张不超过 10 MB</small></span>
        </label>
        <p v-if="imageError || errors.images" id="compose-image-error" class="form-error" role="alert">{{ imageError || errors.images }}</p>
        <ol v-if="images.length" class="compose-gallery" aria-label="图片预览顺序">
          <li v-for="(photo,index) in images" :key="photo.id" class="compose-photo">
            <figure><img :src="photo.url" :alt="photo.name"><figcaption v-if="index === 0" class="tag">封面</figcaption></figure>
            <div class="compose-photo-controls">
              <button type="button" class="icon-button" :aria-label="`前移第 ${index + 1} 张图片`" :disabled="index === 0" @click="move(index,-1)"><AppIcon name="up" /></button>
              <button type="button" class="icon-button" :aria-label="`后移第 ${index + 1} 张图片`" :disabled="index === images.length - 1" @click="move(index,1)"><AppIcon name="down" /></button>
              <button type="button" class="icon-button" :aria-label="`删除第 ${index + 1} 张图片`" @click="remove(index)"><AppIcon name="close" /></button>
            </div>
          </li>
        </ol>
      </section>
      <section class="compose-fields stack" aria-label="帖子内容">
        <div class="field"><label for="compose-title">帖子标题</label><input id="compose-title" v-model="draft.title" class="control" required placeholder="给这套穿搭起个名字" :aria-invalid="!!errors.title" :aria-describedby="errors.title ? 'compose-title-error' : undefined" @blur="touched.title = true"><p v-if="errors.title" id="compose-title-error" class="form-error">{{ errors.title }}</p></div>
        <div class="field"><label for="compose-text">帖子正文</label><textarea id="compose-text" v-model="draft.text" class="control" rows="5" required placeholder="记录这套搭配的细节" :aria-invalid="!!errors.text" :aria-describedby="errors.text ? 'compose-text-error' : undefined" @blur="touched.text = true" /><p v-if="errors.text" id="compose-text-error" class="form-error">{{ errors.text }}</p></div>
        <div class="field"><label for="compose-type">帖子类型</label><select id="compose-type" v-model="draft.post_type" class="control"><option value="outfit">穿搭推荐</option><option value="help">个人求助</option></select></div>
        <div class="field"><label for="compose-tags">穿搭标签 <small class="muted">选填</small></label><input id="compose-tags" v-model="draft.tags" class="control" placeholder="通勤，叠穿" aria-describedby="compose-tag-hint"><p id="compose-tag-hint" class="meta">用逗号分隔多个标签。</p><div v-if="tags.length" class="choice-wrap"><span v-for="tag in tags" :key="tag" class="tag compose-tag">{{ tag }}</span></div></div>
        <div class="compose-relation"><strong class="body-small">关联搭配 <small class="muted">选填</small></strong><p class="meta">仅可关联本人公开单品。关联入口待接入。</p></div>
        <div class="compose-actions"><AppButton type="submit" variant="secondary" :disabled="checking">检查预览</AppButton><AppButton disabled aria-describedby="compose-status">发布 · 待接入</AppButton></div>
      </section>
    </form>
    <AppSheet :model-value="asking" title="放弃本次编辑？" @update:model-value="open => { if (!open) leave(false) }">
      <p class="body-small muted">离开后会清除这次编辑的文字和图片。</p>
      <div class="actions"><AppButton variant="secondary" @click="leave(false)">继续编辑</AppButton><AppButton @click="leave(true)">放弃并离开</AppButton></div>
    </AppSheet>
  </section>
</template>
