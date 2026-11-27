<script setup>
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, changePassword, loadIdentity, session } from '../api/session'
import { describeError } from '../api/http'
import { validEmail } from '../api/validation'
import { notify } from '../composables/useFeedback'
import AppButton from '../components/AppButton.vue'
import AppIcon from '../components/AppIcon.vue'
import StatusPanel from '../components/StatusPanel.vue'
const router = useRouter()
const form = reactive({ nickname:'', email:'' })
const password = reactive({ oldPassword:'', newPassword:'', confirm:'' })
const busy = ref(false)
const error = ref('')
const passwordError = ref('')
watch(() => session.user, user => { if (user) Object.assign(form, {nickname:user.nickname,email:user.email}) }, {immediate:true})
async function saveProfile() {
  error.value = ''
  const email = form.email.trim().toLowerCase()
  const nickname = form.nickname.trim()
  if (!nickname || !validEmail(email)) { error.value = '请填写昵称和有效邮箱'; return }
  const body = {}
  if (nickname !== session.user.nickname) body.nickname = nickname
  if (email !== session.user.email) body.email = email
  if (!Object.keys(body).length) { notify('资料没有变化'); return }
  busy.value = true
  try { session.user = await api('/me',{method:'PATCH',body}); notify('资料已保存') }
  catch (problem) { if (problem.kind !== 'stale') error.value = describeError(problem) }
  finally { busy.value = false }
}
async function savePassword() {
  const length = Array.from(password.newPassword).length
  if (!password.oldPassword || length < 8 || length > 128 || password.newPassword !== password.confirm) {
    passwordError.value = '请填写旧密码、8 至 128 字符的新密码，并确认两次一致。'; return
  }
  busy.value = true
  passwordError.value = ''
  try {
    await changePassword({oldPassword:password.oldPassword,newPassword:password.newPassword})
    notify('密码已修改，请重新登录')
    await router.replace('/login')
  } catch (problem) { if (problem.kind !== 'stale') passwordError.value = describeError(problem) }
  finally { busy.value = false }
}
</script>
<template>
  <section class="screen screen-form"><div class="page-lead"><h1 class="display">账号管理</h1></div>
    <StatusPanel v-if="!session.user" retry title="暂未读取账号资料" :message="session.detailsError" @retry="loadIdentity" />
    <template v-else>
      <form class="stack" @submit.prevent="saveProfile">
        <div class="field"><label for="account-nickname">昵称</label><input id="account-nickname" class="control" v-model="form.nickname" maxlength="30" required></div>
        <div class="field"><label for="account-email">邮箱</label><input id="account-email" class="control" v-model="form.email" type="email" autocomplete="email" maxlength="254" required></div>
        <p class="notice"><AppIcon name="info" />{{ !session.config ? '正在确认头像关联状态' : session.config.avatarUpdateEnabled ? '本轮未开放头像编辑' : '头像关联待接入' }}</p>
        <p v-if="error" class="notice is-error" role="alert">{{ error }}</p>
        <AppButton type="submit" :disabled="busy">保存资料</AppButton>
      </form>
      <form class="section stack border-section" @submit.prevent="savePassword">
        <h2 class="section-title">修改密码</h2>
        <div class="field"><label for="old-password">旧密码</label><input id="old-password" class="control" v-model="password.oldPassword" type="password" maxlength="128" autocomplete="current-password" required></div>
        <div class="field"><label for="new-password">新密码</label><input id="new-password" class="control" v-model="password.newPassword" type="password" minlength="8" maxlength="128" autocomplete="new-password" required></div>
        <div class="field"><label for="check-password">确认新密码</label><input id="check-password" class="control" v-model="password.confirm" type="password" maxlength="128" autocomplete="new-password" required></div>
        <p v-if="passwordError" class="notice is-error" role="alert">{{ passwordError }}</p>
        <AppButton type="submit" variant="secondary" :disabled="busy">修改密码</AppButton>
      </form>
    </template>
  </section>
</template>
