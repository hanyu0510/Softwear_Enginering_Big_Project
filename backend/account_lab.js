const $ = selector => document.querySelector(selector);
const tokenKey = 'account_access_token';
let refreshInFlight = null;
let refreshDisabled = false;

function status(message) {$('#status').textContent = message;}
function showResult(path, data) {
  const safe = JSON.parse(JSON.stringify(data));
  if (safe.data?.token) safe.data.token = '[access token 已保存，不在页面展示]';
  $('#result').textContent = path + '\n' + JSON.stringify(safe, null, 2);
}
function clearLogin() {sessionStorage.removeItem(tokenKey); $('#identity').textContent = '当前未登录';}
function saveToken(data) {sessionStorage.setItem(tokenKey, data.token);}
function jsonRequest(body, method = 'POST') {return {method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};}

async function refreshToken() {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const response = await fetch('/api/v1/auth/refresh', {method:'POST',credentials:'include'});
      const payload = await response.json();
      if (payload.code !== 0) {
        if (payload.code === 40101) {clearLogin(); refreshDisabled = true;}
        throw new Error(payload.message + ' / ' + payload.requestId);
      }
      saveToken(payload.data);
      return payload;
    })().finally(() => {refreshInFlight = null;});
  }
  return refreshInFlight;
}

async function api(path, options={}, retry=true) {
  const token = sessionStorage.getItem(tokenKey);
  const headers = {...(options.headers || {})};
  if (token) headers.Authorization = 'Bearer ' + token;
  const response = await fetch('/api/v1'+path, {...options,headers,credentials:'include'});
  const payload = await response.json();
  const excluded = ['/auth/login','/auth/register','/auth/forgot-password','/auth/refresh','/auth/logout'];
  if (payload.code === 40101 && retry && !excluded.includes(path) && !refreshDisabled) {
    await refreshToken();
    return api(path,options,false);
  }
  showResult(path,payload);
  if (payload.code !== 0) throw new Error(payload.message+' / '+payload.requestId);
  return payload;
}

async function run(button, fn) {
  if (button) button.disabled = true;
  try {await fn();} catch (error) {status(error.message || '网络请求失败，请确认后台仍在运行');}
  finally {if (button) button.disabled = false;}
}
async function loadMe() {
  const payload = await api('/me');
  $('#identity').textContent = `当前用户：${payload.data.nickname} / ${payload.data.email} / ${payload.data.id}`;
  return payload;
}
function formAction(id, fn) {
  $(id).addEventListener('submit', event => {
    event.preventDefault();
    run(event.submitter, () => fn(Object.fromEntries(new FormData(event.target)), event.target));
  });
}

formAction('#register-form', async (body, form) => {
  await api('/auth/register',jsonRequest(body));
  form.reset();
  $('#login-form').elements.email.value = body.email;
  $('#login-form').elements.password.value = '';
  // 验收页为单页面，跳到登录区域；正式前端在这里用 Router 跳转登录页。
  location.hash = 'login-panel';
  $('#login-form').elements.password.focus();
  status('注册成功，请在登录区域输入密码登录。没有自动登录。');
});
formAction('#login-form', async (body, form) => {
  const payload = await api('/auth/login',jsonRequest(body));
  saveToken(payload.data);
  refreshDisabled = false;
  form.elements.password.value = '';
  $('#identity').textContent = `当前用户：${payload.data.user.nickname} / ${payload.data.user.email} / ${payload.data.user.id}`;
  status('登录成功，access token 已保存；refresh token 由后端 Cookie 管理。');
});
$('#refresh').addEventListener('click', event => run(event.target,async () => {
  const payload = await refreshToken();
  refreshDisabled = false;
  showResult('/auth/refresh',payload);
  status('刷新成功，两种凭据已轮换，7天期限不顺延。');
}));
$('#logout').addEventListener('click', event => run(event.target,async () => {
  await api('/auth/logout',{method:'POST'});
  clearLogin(); refreshDisabled = true;
  status('已退出当前会话。');
}));
$('#me').addEventListener('click', event => run(event.target,loadMe));
formAction('#profile-form',async (body,form) => {
  const fields = Object.fromEntries(Object.entries(body).filter(([,value])=>value.trim()!==''));
  const result = await api('/me',jsonRequest(fields,'PATCH'));
  $('#identity').textContent = `当前用户：${result.data.nickname} / ${result.data.email} / ${result.data.id}`;
  form.reset(); status('资料保存成功。修改邮箱不会退出当前会话。');
});
formAction('#password-form',async (body,form) => {
  await api('/me/change-password',jsonRequest(body));
  clearLogin(); refreshDisabled = true; form.reset();
  status('密码修改成功，全部旧登录凭据失效，请重新登录。');
});
formAction('#forgot-form',async (body,form) => {
  await api('/auth/forgot-password',jsonRequest(body));
  clearLogin(); refreshDisabled = true; form.reset();
  status('密码重置成功，请用新密码登录。');
});
for (const button of document.querySelectorAll('[data-read]')) button.addEventListener('click',event=>run(event.target,()=>api(button.dataset.read)));
for (const [id,method] of [['#follow','POST'],['#unfollow','DELETE']]) $(id).addEventListener('click',event=>run(event.target,async()=>{
  const id = $('#target-user').value.trim();
  if (!id) throw new Error('请填写对方用户ID');
  await api(`/users/${encodeURIComponent(id)}/follow`,{method});
  status(method==='POST'?'关注操作成功':'取消关注成功');
}));
$('#mark-read').addEventListener('click',event=>run(event.target,async()=>{
  const id = $('#notification-id').value.trim();
  if (!id) throw new Error('请填写通知ID');
  await api(`/notifications/${encodeURIComponent(id)}/read`,{method:'PUT'});
  status('已标记为已读');
}));
formAction('#preferences-form',async body=>{
  await api('/me/style-preferences',jsonRequest({styles:[body.style],avoid_colors:[],notes:body.notes},'PUT'));
  status('偏好已保存。避开颜色等待团队白名单后接入。');
});
$('#preferences-read').addEventListener('click',event=>run(event.target,()=>api('/me/style-preferences')));

// 页面重新打开：有access则查询本人；没有则只尝试一次刷新，不循环。
run(null,async()=>{
  if (!sessionStorage.getItem(tokenKey)) {
    try {await refreshToken();}
    catch(error) {if (refreshDisabled) {status('当前未登录，请先注册或登录。'); return;} throw error;}
  }
  await loadMe();
});
