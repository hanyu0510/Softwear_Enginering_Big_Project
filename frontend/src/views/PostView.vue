<script setup>
import { computed, nextTick, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/session'
import { describeError } from '../api/http'
import { courseEnabled } from '../api/capabilities'
import { useRequest } from '../composables/useRequest'
import AppButton from '../components/AppButton.vue'
import AppIcon from '../components/AppIcon.vue'
import AppImage from '../components/AppImage.vue'
import PostActions from '../components/PostActions.vue'
import StatusPanel from '../components/StatusPanel.vue'

const base = '/posts/' + encodeURIComponent(useRoute().params.id)
const { data: post, busy, error, run } = useRequest(signal => api(base, { signal }))
const { data: comments, busy: loadingComments, error: commentsError, run: loadComments } = useRequest(signal => api(base + '/comments?page=1&pageSize=100', { signal }))
const current = ref(0)
const input = ref()
const text = ref('')
const failure = ref('')
const sending = ref(false)
const gallery = computed(() => post.value?.images?.length ? post.value.images.map(image => image.url) : post.value?.image_urls || [])
run()
loadComments()
function turn(offset) { current.value = (current.value + offset + gallery.value.length) % gallery.value.length }
function focusComment() { input.value?.focus(); input.value?.scrollIntoView({ block:'center' }) }
async function comment() {
  const content = text.value.trim()
  if (!content) { failure.value = '请先填写评论内容'; focusComment(); return }
  if (sending.value) return
  sending.value = true
  failure.value = ''
  try {
    await api(base + '/comments', { method:'POST', body:{ text: content } })
    text.value = ''
    await Promise.all([loadComments(),run()])
    await nextTick()
    focusComment()
  } catch (error) { if (error.kind !== 'stale') failure.value = describeError(error) }
  finally { sending.value = false }
}
</script>

<template>
  <section v-if="error || busy && !post" class="screen narrow"><StatusPanel :loading="busy && !post" :error="!!error" :retry="!!error" :message="error" @retry="run" /></section>
  <article v-else-if="post" class="screen post-detail">
    <div class="post-feature">
      <div class="gallery">
        <AppImage class="gallery-frame" :path="gallery[current]" :alt="post.title" eager />
        <div v-if="gallery.length > 1" class="gallery-controls"><button class="icon-button" type="button" aria-label="上一张图片" @click="turn(-1)"><AppIcon name="back" /></button><span class="meta">{{ current + 1 }} / {{ gallery.length }}</span><button class="icon-button" type="button" aria-label="下一张图片" @click="turn(1)"><AppIcon name="next" /></button></div>
      </div>
      <div class="detail-text">
        <div class="byline"><AppImage class="avatar medium" :path="post.author?.avatar_url" /><div><strong class="body-small">{{ post.author?.nickname }}</strong><p v-if="courseEnabled && post.id.startsWith('course_')" class="meta">课程样本帖子</p></div></div>
        <h1 class="display">{{ post.title }}</h1><p>{{ post.text }}</p><div class="actions"><span v-for="tag in post.tags" :key="tag" class="tag">{{ tag }}</span></div>
      </div>
    </div>
    <section class="section border-section">
      <h2 class="section-title">评论 {{ comments?.total ?? post.comment_count }}</h2>
      <StatusPanel v-if="loadingComments && !comments || commentsError" :loading="loadingComments" :error="!!commentsError" :retry="!!commentsError" :message="commentsError" @retry="loadComments" />
      <ul v-else-if="comments?.list.length" class="comment-list">
        <li v-for="entry in comments.list" :key="entry.id">
          <div class="byline">
            <AppImage class="avatar" :path="entry.author?.avatar_url" />
            <strong class="body-small">{{ entry.author?.nickname }}</strong>
            <span v-if="courseEnabled && entry.id.startsWith('course_note_')" class="tag">课程样本评论</span>
          </div>
          <p>{{ entry.text }}</p>
        </li>
      </ul>
      <p v-else class="muted body-small">还没有评论。</p>
      <form class="comment-form" @submit.prevent="comment">
        <label for="comment-text" class="field-label body-small">发表你的评论</label><input id="comment-text" ref="input" v-model="text" class="control" placeholder="分享你喜欢的搭配细节" maxlength="500">
        <AppButton type="submit" :busy="sending">发送</AppButton><p v-if="failure" class="form-error" role="alert">{{ failure }}</p>
      </form>
    </section>
    <footer class="post-dock"><div class="post-dock-inner"><PostActions :post="post" detail @update="patch => post = {...post,...patch}" @comment="focusComment" /></div></footer>
  </article>
</template>
