<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login, register, resetPassword, session } from '../api/session'
import { describeError } from '../api/http'
import { validEmail } from '../api/validation'
import { notify } from '../composables/useFeedback'
import AppButton from './AppButton.vue'
import AppIcon from './AppIcon.vue'
import loginPhoto from '../assets/auth/login.png'
import registerPhoto from '../assets/auth/register.png'

const props = defineProps({ mode: { type: String, required: true } })
const route = useRoute()
const router = useRouter()
const modes = {
  login: { title: '欢迎回来', hint: '登录后继续整理衣橱、探索搭配。', submit: '登录' },
  register: { title: '创建账号', hint: '创建你的个人衣橱。', submit: '创建账号' },
  reset: { title: '重置密码', hint: '填写账号邮箱和新密码。', submit: '重置密码' },
}
const mode = computed(() => modes[props.mode])
const isLogin = computed(() => props.mode === 'login')
const data = reactive({ email: typeof route.query.email === 'string' ? route.query.email : '', nickname: '', password: '', confirmation: '' })
const errors = reactive({})
const show = reactive({ password: false, confirmation: false })
const form = ref()
const busy = ref(false)
const message = ref('')
const fields = computed(() => [
  ...(props.mode === 'register' ? [{ id: 'nickname', label: '昵称', type: 'text', max: 30, autocomplete: 'nickname' }] : []),
  { id: 'email', label: '邮箱', type: 'email', max: 254, autocomplete: isLogin.value ? 'username' : 'email', placeholder: 'name@example.com' },
  { id: 'password', label: isLogin.value ? '密码' : '新密码', type: 'password', max: 128, autocomplete: isLogin.value ? 'current-password' : 'new-password', placeholder: isLogin.value ? '输入密码' : '至少 8 个字符' },
  ...(!isLogin.value ? [{ id: 'confirmation', label: '确认密码', type: 'password', max: 128, autocomplete: 'new-password' }] : []),
])

async function submit() {
  const email = data.email.trim().toLowerCase()
  const nickname = data.nickname.trim()
  message.value = ''
  errors.nickname = props.mode === 'register' && !nickname ? '请输入昵称。' : ''
  errors.email = validEmail(email) ? '' : '请输入有效的邮箱地址。'
  const length = Array.from(data.password).length
  errors.password = length >= (isLogin.value ? 1 : 8) && length <= 128 ? '' : isLogin.value ? '请输入密码。' : '请输入 8 至 128 个字符。'
  errors.confirmation = !isLogin.value && data.password !== data.confirmation ? '两次密码不一致。' : ''
  const first = fields.value.find(field => errors[field.id])
  if (first) { await nextTick(); form.value.elements.namedItem(first.id)?.focus(); return }
  busy.value = true
  try {
    const next = typeof route.query.next === 'string' && router.resolve(route.query.next).meta.private ? route.query.next : '/home'
    if (isLogin.value) {
      await login({ email, password: data.password })
      await router.replace(next)
    } else {
      if (props.mode === 'register') await register({ email, nickname, password: data.password })
      else await resetPassword({ email, newPassword: data.password })
      notify(props.mode === 'register' ? '账号已创建，请登录' : '密码已重置，请重新登录')
      await router.replace({ path: '/login', query: { email, next } })
    }
  } catch (error) {
    if (error.kind !== 'stale') message.value = describeError(error)
  } finally { busy.value = false }
}
</script>

<template>
  <section class="auth-layout">
    <figure :class="['auth-photo', { register: !isLogin }]"><img :src="isLogin ? loginPhoto : registerPhoto" alt="" fetchpriority="high"></figure>
    <div class="auth-panel">
      <div class="page-lead"><h1 class="display">{{ mode.title }}</h1><p class="body-small muted">{{ mode.hint }}</p></div>
      <p v-if="route.query.expired" class="notice is-warning" role="status">会话已过期，请重新登录。</p>
      <p v-else-if="session.message" class="notice is-warning" role="status">{{ session.message }}</p>
      <form ref="form" class="auth-form stack" novalidate @submit.prevent="submit">
        <div v-for="field in fields" :key="field.id" class="field">
          <label :for="field.id">{{ field.label }}</label>
          <div :class="{ 'field-with-action': field.type === 'password' }">
            <input class="control" v-model="data[field.id]" :id="field.id" :name="field.id" :type="show[field.id] ? 'text' : field.type"
              :maxlength="field.max" :autocomplete="field.autocomplete" :placeholder="field.placeholder" required
              :aria-invalid="!!errors[field.id]" :aria-describedby="errors[field.id] ? field.id + '-error' : undefined" @input="errors[field.id] = ''">
            <button v-if="field.type === 'password'" type="button" class="icon-button" :aria-label="show[field.id] ? '隐藏' + field.label : '显示' + field.label" @click="show[field.id] = !show[field.id]">
              <AppIcon :name="show[field.id] ? 'eyeOff' : 'eye'" />
            </button>
          </div>
          <p v-if="errors[field.id]" :id="field.id + '-error'" class="form-error">{{ errors[field.id] }}</p>
        </div>
        <p v-if="message" class="notice is-error wrap" role="alert">{{ message }}</p>
        <AppButton type="submit" class="full" :busy="busy">{{ mode.submit }}</AppButton>
      </form>
      <nav class="auth-links" aria-label="账号导航">
        <template v-if="isLogin">
          <RouterLink class="text-button" :to="{path:'/register',query:{next:route.query.next}}">创建账号</RouterLink>
          <RouterLink class="text-button" :to="{path:'/forgot-password',query:{next:route.query.next}}">忘记密码</RouterLink>
        </template>
        <RouterLink v-else class="text-button" :to="{path:'/login',query:{next:route.query.next}}">返回登录</RouterLink>
      </nav>
    </div>
  </section>
</template>
