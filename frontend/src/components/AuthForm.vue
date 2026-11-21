<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import loginHero from '../assets/auth/login.png'
import registerHero from '../assets/auth/register.png'

const props = defineProps({
  mode: { type: String, required: true },
})
const router = useRouter()
const form = reactive({})
const visiblePasswords = reactive({})
const message = ref('')

const phone = { key: 'phone', label: '请输入手机号', type: 'tel', icon: 'mobile', autocomplete: 'tel' }
const password = { key: 'password', label: '请输入密码', type: 'password', icon: 'lock-on', autocomplete: 'current-password' }
const confirmation = { ...password, key: 'confirmation', label: '请再次输入密码', autocomplete: 'new-password' }

const fields = computed(() => ({
  login: [
    { key: 'account', label: '请输入手机号或邮箱', type: 'text', icon: 'mail', autocomplete: 'username' },
    password,
  ],
  register: [
    { key: 'nickname', label: '请输入昵称', type: 'text', icon: 'user', autocomplete: 'nickname' },
    phone,
    { ...password, label: '设置登录密码', autocomplete: 'new-password' },
    confirmation,
  ],
  reset: [
    phone,
    { ...password, label: '设置新密码', autocomplete: 'new-password' },
    { ...confirmation, label: '请再次确认新密码' },
  ],
}[props.mode]))

const action = computed(() => ({
  login: '登录',
  register: '创建账号',
  reset: '重置密码',
}[props.mode]))

function validPhone() {
  return /^1[3-9]\d{9}$/.test(form.phone?.trim() ?? '')
}

function submit() {
  message.value = ''
  if (props.mode === 'login') {
    router.push('/home')
    return
  }
  if (!validPhone()) {
    message.value = '请输入有效的手机号。'
    return
  }
  if (form.password !== form.confirmation) {
    message.value = '两次输入的密码不一致。'
    return
  }
  message.value = props.mode === 'register'
    ? '注册表单验证通过。你可以返回登录页继续演示。'
    : '重置密码表单验证通过。你可以返回登录页继续演示。'
}
</script>

<template>
  <section class="auth" :class="'auth--' + mode" :aria-label="action">
    <header v-if="mode !== 'reset'" class="hero">
      <img :src="mode === 'login' ? loginHero : registerHero" alt="" />
      <div class="wordmark">
        <h1>衣搭</h1>
        <span>YIDA</span>
        <p>{{ mode === 'login' ? '发现更好的穿搭灵感' : '用穿搭记录生活' }}</p>
      </div>
    </header>
    <header v-else class="reset-heading">
      <RouterLink class="back" to="/login" aria-label="返回登录">←</RouterLink>
      <h1>重置密码</h1>
      <p>填写手机号并设置新的登录密码</p>
    </header>

    <form class="panel" @submit.prevent="submit">
      <div v-for="field in fields" :key="field.key" class="field">
        <t-icon :name="field.icon" aria-hidden="true" />
        <input
          v-model="form[field.key]"
          :type="visiblePasswords[field.key] ? 'text' : field.type"
          :placeholder="field.label"
          :aria-label="field.label"
          :autocomplete="field.autocomplete"
          :minlength="mode !== 'login' && field.type === 'password' ? 6 : undefined"
          required
        />
        <button
          v-if="field.type === 'password'"
          type="button"
          class="visibility"
          :aria-label="visiblePasswords[field.key] ? '隐藏密码' : '显示密码'"
          @click="visiblePasswords[field.key] = !visiblePasswords[field.key]"
        >
          <t-icon :name="visiblePasswords[field.key] ? 'browse' : 'browse-off'" />
        </button>
      </div>

      <label v-if="mode === 'register'" class="agreement">
        <input type="checkbox" required />
        <span>我已阅读并同意 <strong>《衣搭用户协议》</strong>和<strong>《隐私政策》</strong></span>
      </label>

      <button class="submit" type="submit">{{ action }}</button>
      <p v-if="message" class="message" role="status">{{ message }}</p>

      <nav v-if="mode === 'login'" class="auth-links" aria-label="账号帮助">
        <RouterLink to="/register">注册新账号</RouterLink>
        <RouterLink to="/forgot-password">忘记密码？</RouterLink>
      </nav>
      <nav v-else-if="mode === 'register'" class="auth-links">
        <RouterLink to="/login">已有账号？返回登录</RouterLink>
      </nav>
    </form>
  </section>
</template>

<style scoped>
.auth {
  --accent: #ec7057;
  --ink: #252522;
  --paper: #faf7f2;
  max-width: 440px;
  min-height: 100dvh;
  margin: auto;
  background: var(--paper);
  color: var(--ink);
}

.hero {
  position: relative;
  height: clamp(285px, 56svh, 510px);
}

.auth--register .hero {
  height: clamp(205px, 32svh, 300px);
}

.hero img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 42%;
}

.wordmark {
  position: absolute;
  top: 19%;
  left: 8%;
}

.wordmark h1,
.wordmark span {
  margin: 0;
  font-family: "Songti SC", "Noto Serif SC", serif;
  font-weight: 800;
}

.wordmark h1 { font-size: 44px; line-height: 1; }
.wordmark span { letter-spacing: .24em; padding-left: 6px; }
.wordmark p { margin: 16px 0 0; font-size: 14px; }
.wordmark p::after {
  content: '';
  display: block;
  width: 32px;
  height: 3px;
  margin-top: 14px;
  background: var(--accent);
}

.panel {
  position: relative;
  margin-top: -20px;
  padding: 36px 20px 28px;
  border-radius: 24px 24px 0 0;
  background: var(--paper);
}

.auth--register .panel { padding-top: 28px; }
.auth--reset .panel { margin: 0; padding-top: 18px; }
.reset-heading { position: relative; padding: 104px 20px 16px; text-align: center; }
.reset-heading h1 { margin: 0; font-size: 28px; }
.reset-heading p { color: #686662; font-size: 15px; }
.back { position: absolute; top: 42px; left: 20px; font-size: 28px; }

.field {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 50px;
  padding: 0 13px;
  margin-bottom: 13px;
  border: 1px solid #e3ddd6;
  border-radius: 15px;
  font-size: 20px;
}

.field:focus-within { border-color: var(--accent); }
.field input {
  flex: 1;
  width: 0;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--ink);
  font: inherit;
  font-size: 15px;
}

button { cursor: pointer; font: inherit; }
.visibility { display: grid; place-items: center; padding: 5px; border: 0; background: none; color: inherit; }
.agreement { display: flex; align-items: center; gap: 6px; margin-top: 22px; font-size: 12px; }
.agreement input { accent-color: var(--accent); }
.agreement strong { color: #b54430; }

.submit {
  width: 100%;
  min-height: 50px;
  margin-top: 20px;
  border: 0;
  border-radius: 999px;
  background: linear-gradient(100deg, #e46548, var(--accent));
  color: #fff;
  font-size: 20px;
  font-weight: 700;
}

.auth--reset .submit { margin-top: 48px; }
.auth-links { display: flex; justify-content: center; margin-top: 24px; font-size: 14px; font-weight: 600; }
a { color: inherit; text-decoration: none; }
.auth-links a { padding: 0 18px; }
.auth-links a + a { border-left: 1px solid #ded6ce; }
.message { font-size: 14px; color: #95402d; }
</style>
