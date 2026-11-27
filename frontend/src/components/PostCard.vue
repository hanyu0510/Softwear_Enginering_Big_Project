<script setup>
import AppImage from './AppImage.vue'
import PostActions from './PostActions.vue'
defineProps({ post: { type: Object, required: true }, eager: Boolean })
defineEmits(['update'])
</script>
<template>
  <article class="post-card">
    <RouterLink class="post-photo" :to="'/posts/' + post.id" :style="{ '--photo-ratio': post.images?.[0]?.aspect_ratio || 0.8 }" :aria-label="'查看' + post.title">
      <AppImage :path="post.images?.[0]?.thumb_url || post.image_urls?.[0]" :alt="post.title" :eager="eager" />
    </RouterLink>
    <div class="post-card-content">
      <h2><RouterLink :to="'/posts/' + post.id">{{ post.title }}</RouterLink></h2>
      <div class="byline"><AppImage class="avatar" :path="post.author?.avatar_url" /><span class="meta">{{ post.author?.nickname }}</span><span v-if="post.tags?.[0]" class="meta">· {{ post.tags[0] }}</span></div>
      <PostActions :post="post" @update="$emit('update', $event)" />
    </div>
  </article>
</template>
