<script setup>
import { computed, onScopeDispose, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import { courseEnabled } from '../api/capabilities'
import { useRequest } from '../composables/useRequest'
import AppButton from '../components/AppButton.vue'
import AppIcon from '../components/AppIcon.vue'
import AppSheet from '../components/AppSheet.vue'
import StatusPanel from '../components/StatusPanel.vue'
import WeatherLine from '../components/WeatherLine.vue'

const router = useRouter()
const course = shallowRef()
const providerError = ref('')
if (import.meta.env.DEV && import.meta.env.VITE_COURSE_DEMO === '1') {
  import('../api/course').then(module => { course.value = module }, () => { providerError.value = '课程推荐模块加载失败，请刷新重试' })
}
const draft = computed(() => course.value?.courseDraft)
const cityPicker = ref(false)
const keyword = ref('')
const validation = ref('')
const sceneChoices = ['日常通勤','公园野餐拍照','周末咖啡馆']
const styleChoices = ['美拉德','极简','复古']
const queryCities = useRequest((signal, search) => course.value.cities(search, signal))
const queryWeather = useRequest((signal, city, day) => course.value.weather(city, day, signal))
const generate = useRequest((signal, body) => course.value.createRecommendation(body, signal))
const today = computed(() => course.value?.chinaDate())
const target = computed(() => draft.value?.travel ? [draft.value.destination?.cityId,draft.value.travelDate] : ['city_suzhou',today.value])
watch(target, ([city,day]) => {
  queryWeather.cancel()
  if (course.value && city && day) queryWeather.run(city,day)
}, {immediate:true})
watch(cityPicker, open => { if (open) { keyword.value = ''; queryCities.run('') } })
let typing
onScopeDispose(() => clearTimeout(typing))
function searchCity() {
  clearTimeout(typing)
  typing = setTimeout(() => { if (cityPicker.value) queryCities.run(keyword.value.trim()) }, 200)
}
function selectCity(city) { draft.value.destination = city; cityPicker.value = false }
function toggleTravel() {
  const form = draft.value
  form.travel = !form.travel
  if (!form.travel) { form.destination = null; form.travelDate = '' }
  else form.travelDate ||= today.value
}
async function submit() {
  validation.value = ''
  const form = draft.value
  if (form.travel && !form.destination) { validation.value = '请选择目的地后再生成'; document.getElementById('choose-city')?.focus(); return }
  if (form.travel && (!form.travelDate || form.travelDate < today.value || form.travelDate > course.value.chinaDate(14))) {
    validation.value = '出行日期需在今天起 14 天内'; document.getElementById('trip-date')?.focus(); return
  }
  const body = { sceneText:form.sceneText.trim(), styleText:form.styleText.trim(), wardrobeScope:'owned_and_wish' }
  if (form.travel) Object.assign(body, { destination:{ cityId:form.destination.cityId }, travelDate:form.travelDate })
  const result = await generate.run(body)
  if (result?.id) router.push('/outfit/results/' + result.id)
}
</script>

<template>
  <section class="screen recommendation-screen">
    <div class="recommend-layout">
      <aside class="recommend-aside" aria-labelledby="recommendation-heading">
        <div class="recommend-hero">
          <div class="recommend-hero-copy"><h1 id="recommendation-heading" class="display">今天穿什么？</h1><p class="body-small muted">从场景、风格和天气挑出今天的一套。</p></div>
          <figure v-if="course" class="recommend-hero-img"><img :src="'/__course/media/look-11.webp'" alt="暖中性色衣架陈列"></figure>
        </div>
        <div v-if="course" class="recommend-context">
          <p class="notice"><AppIcon name="info" /><span>独立规则推荐 · 样本衣橱 · 模拟天气。现场新增的衣物暂未参与本次推荐。</span></p>
          <WeatherLine :weather="queryWeather.data.value" :pending="!!target[0] && queryWeather.busy.value" :problem="!target[0] ? '选择目的地与日期后查看模拟天气' : queryWeather.error.value" />
        </div>
      </aside>
      <StatusPanel v-if="!course" class="recommend-form" :loading="courseEnabled && !providerError" title="推荐暂未开放" :message="providerError || (!courseEnabled ? '公共推荐接口仍在接入中。' : '')" />
      <form v-else class="recommend-form" novalidate @submit.prevent="submit">
        <div class="stack">
          <div class="field">
            <label for="scene">今天有什么安排？</label><textarea id="scene" v-model="draft.sceneText" class="control" placeholder="例如：公园野餐拍照" maxlength="300" />
            <div class="choice-wrap"><button v-for="word in sceneChoices" :key="word" type="button" class="choice" :aria-pressed="draft.sceneText === word" @click="draft.sceneText = draft.sceneText === word ? '' : word"><span>{{ word }}</span></button></div>
          </div>
          <div class="field">
            <label for="outfit-style">想穿什么风格？</label><input id="outfit-style" v-model="draft.styleText" class="control" placeholder="例如：美拉德" maxlength="300">
            <div class="choice-wrap"><button v-for="word in styleChoices" :key="word" type="button" class="choice" :aria-pressed="draft.styleText === word" @click="draft.styleText = draft.styleText === word ? '' : word"><span>{{ word }}</span></button></div>
          </div>
          <div class="toggle-row"><div><strong class="body-small">旅行搭配</strong><p class="meta">按目的地和日期规划衣着</p></div><button type="button" class="switch" role="switch" aria-label="旅行搭配" :aria-checked="draft.travel" @click="toggleTravel"><span class="switch-track" /></button></div>
          <Transition name="travel"><div v-if="draft.travel" class="fields-pair">
            <div class="field"><span class="field-label">目的地</span><AppButton id="choose-city" variant="secondary" @click="cityPicker = true">{{ draft.destination?.cityName || '选择城市' }}</AppButton></div>
            <div class="field"><label for="trip-date">出行日期</label><input id="trip-date" class="control" type="date" v-model="draft.travelDate" :min="today" :max="course.chinaDate(14)"></div>
          </div></Transition>
          <p v-if="validation || generate.error.value" class="notice is-error" role="alert">{{ validation || generate.error.value }}</p>
          <AppButton type="submit" class="full" :busy="generate.busy.value"><AppIcon name="sparkle" />{{ generate.busy.value ? '正在生成搭配' : generate.error.value ? '重试生成' : '生成搭配' }}</AppButton>
          <RouterLink v-if="generate.error.value" to="/outfit/results/backup" class="button secondary">查看只读备用样例</RouterLink>
        </div>
      </form>
    </div>
    <AppSheet v-if="course" v-model="cityPicker" title="搜索城市">
      <div class="field"><label for="city-keyword">城市名称</label><input id="city-keyword" v-model="keyword" type="search" class="control" placeholder="例如：苏州、罗马" maxlength="80" @input="searchCity"></div>
      <StatusPanel v-if="queryCities.busy.value || queryCities.error.value" :loading="queryCities.busy.value" :error="!!queryCities.error.value" :retry="!!queryCities.error.value" :message="queryCities.error.value" @retry="queryCities.run(keyword)" />
      <ul v-else-if="queryCities.data.value?.length" class="sheet-options"><li v-for="city in queryCities.data.value" :key="city.cityId"><button type="button" @click="selectCity(city)">{{ city.cityName }} <small class="meta">{{ city.region }} · {{ city.country }}</small></button></li></ul>
      <p v-else class="body-small muted">没有匹配的城市。</p>
    </AppSheet>
  </section>
</template>
