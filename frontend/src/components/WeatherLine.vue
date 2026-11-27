<script setup>
import AppIcon from './AppIcon.vue'
defineProps({ weather: Object, pending: Boolean, problem: String })
</script>
<template>
  <p class="weather-line icon-sm"><AppIcon name="cloud" />
    <span v-if="weather">{{ weather.cityName }} · {{ weather.date }} · {{ weather.condition }}
      <template v-if="weather.temperatureMinC != null && weather.temperatureMaxC != null"> · {{ weather.temperatureMinC }}–{{ weather.temperatureMaxC }}°C</template>
      · {{ weather.source === 'MOCK_TEST_ONLY' ? '模拟天气' : weather.source || '来源未提供' }}
    </span>
    <span v-else>{{ pending ? '正在读取天气' : problem || '暂无天气数据' }}</span>
  </p>
</template>
