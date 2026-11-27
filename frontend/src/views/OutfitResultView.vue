<script setup>
import { computed, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import { courseEnabled } from '../api/capabilities'
import { labelFor } from '../api/wardrobe'
import { useRequest } from '../composables/useRequest'
import AppImage from '../components/AppImage.vue'
import AppIcon from '../components/AppIcon.vue'
import StatusPanel from '../components/StatusPanel.vue'
import WeatherLine from '../components/WeatherLine.vue'

const id = useRoute().params.id
const course = shallowRef()
const providerError = shallowRef('')
if (import.meta.env.DEV && import.meta.env.VITE_COURSE_DEMO === '1') {
  import('../api/course').then(module => { course.value = module }, () => { providerError.value = '课程推荐模块加载失败，请刷新重试' })
}
const backup = id === 'backup'
const request = useRequest(signal => course.value.readRecommendation(id,signal))
const result = computed(() => !course.value ? null : backup ? course.value.backupResult : request.data.value)
watch(course, value => { if (value && !backup) request.run() })
</script>

<template>
  <section class="screen recommendation-result-screen">
    <div class="page-lead result-lead"><h1 class="display">{{ backup && course ? '只读备用样例' : '今日搭配建议' }}</h1>
      <p v-if="result?.sceneText || result?.styleText" class="body-small muted">{{ [result.sceneText, result.styleText].filter(Boolean).join(' · ') }}</p>
      <p v-if="course" class="notice"><AppIcon name="info" /><span>{{ backup ? '静态备用样例 · 供讲解使用。' : '独立规则推荐 · 样本衣橱 · 模拟天气。现场新增衣物暂未参与。服饰图片为示意。' }}</span></p>
    </div>
    <StatusPanel v-if="!course" :loading="courseEnabled && !providerError" title="推荐结果暂不可用" :message="providerError || (!courseEnabled ? '公共推荐接口仍在接入中。' : '')" />
    <StatusPanel v-else-if="request.busy.value" loading title="正在读取推荐结果" />
    <StatusPanel v-else-if="request.error.value" error retry title="推荐结果加载失败" :message="request.error.value" @retry="request.run">
      <RouterLink to="/outfit/results/backup" class="button secondary">查看只读备用样例</RouterLink>
    </StatusPanel>
    <div v-else-if="result" class="result-layout">
      <div v-if="result.items.length" class="outfit-collage" :class="'pieces-' + result.items.length" aria-label="搭配单品">
        <figure v-for="(item,index) in result.items" :key="item.id" class="collage-tile" :class="'collage-' + index">
          <AppImage :path="course.illustration(item)" :alt="course.displayName(item)" eager />
          <figcaption class="collage-label"><span>{{ course.displayName(item) }}</span><span v-if="item.source === 'wish'" class="tag warning">尚未拥有</span></figcaption>
        </figure>
      </div>
      <StatusPanel v-else title="暂无可展示的搭配" />
      <div class="result-meta">
        <section class="result-reason"><h2 class="section-title">为什么这样搭</h2><p>{{ course.displayReason(result) }}</p></section>
        <section v-if="result.parsed?.style_note || result.parsed?.scene"><h2 class="section-title">场景与风格解析</h2>
          <p v-if="result.parsed.style_note" class="body-small muted">{{ result.parsed.style_note }}</p>
          <p v-if="result.parsed.scene" class="meta">场合 · {{ labelFor('occasions',result.parsed.scene) }}</p>
          <span v-if="result.parsed.low_confidence_fields?.length" class="tag warning">部分输入置信度较低</span>
        </section>
        <section><h2 class="section-title">天气</h2><WeatherLine :weather="result.weather" :problem="backup ? '此备用样例未包含天气' : '服务无天气返回'" /></section>
        <ul v-if="result.warnings?.length || result.local_tips?.length" class="result-notes"><li v-for="line in [...(result.warnings || []), ...(result.local_tips || [])]" :key="line">{{ line }}</li></ul>
        <RouterLink to="/outfit" class="button primary full">返回调整输入</RouterLink>
      </div>
    </div>
  </section>
</template>
