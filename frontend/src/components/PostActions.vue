<script setup>
import { ref } from 'vue'
import { api } from '../api/session'
import { describeError } from '../api/http'
import AppIcon from './AppIcon.vue'
const props = defineProps({ post: { type: Object, required: true }, detail: Boolean })
const emit = defineEmits(['update', 'comment'])
const busy = ref('')
const error = ref('')
async function update(action) {
  if (busy.value) return
  busy.value = action
  error.value = ''
  const liked = action === 'like'
  const exists = liked ? props.post.is_liked : props.post.is_favorited
  try {
    const patch = await api('/posts/' + encodeURIComponent(props.post.id) + '/' + action, { method: exists ? 'DELETE' : 'PUT' })
    emit('update', liked ? { is_liked: patch.is_liked, like_count: patch.like_count } : { is_favorited: patch.is_favorited })
  } catch (problem) { if (problem.kind !== 'stale') error.value = describeError(problem) }
  finally { busy.value = '' }
}
</script>
<template>
  <div class="reaction-bar" :class="{ 'detail-reactions': detail }">
    <button type="button" class="reaction" :aria-label="post.is_liked ? '取消点赞' : '点赞'" :aria-pressed="post.is_liked" :disabled="!!busy" @click="update('like')">
      <AppIcon name="heart" /><span>{{ post.like_count }}</span>
    </button>
    <button type="button" class="reaction" :aria-label="post.is_favorited ? '取消收藏帖子' : '收藏帖子'" :aria-pressed="post.is_favorited" :disabled="!!busy" @click="update('bookmark')">
      <AppIcon name="bookmark" /><span v-if="detail">{{ post.is_favorited ? '已收藏' : '收藏' }}</span>
    </button>
    <button v-if="detail" type="button" class="reaction" aria-label="写评论" @click="$emit('comment')"><AppIcon name="comment" /><span>{{ post.comment_count }}</span></button>
  </div>
  <p v-if="error" class="form-error wrap" role="alert">{{ error }}</p>
</template>
