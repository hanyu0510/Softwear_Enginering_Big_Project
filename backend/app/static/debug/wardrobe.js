const dictionaries = {
  categories: ['tops', 'bottoms', 'outerwear', 'dress', 'shoes', 'bag', 'accessory', 'other'],
  seasons: ['spring', 'summer', 'autumn', 'winter'],
  styles: ['minimal', 'street', 'sweet', 'formal', 'casual', 'vintage', 'sporty'],
  occasions: ['commute', 'date', 'travel', 'casual', 'formal', 'party', 'sport'],
}

const labels = {
  tops: '上装', bottoms: '下装', outerwear: '外套', dress: '连衣裙/套装', shoes: '鞋',
  bag: '包', accessory: '配饰', other: '其他', spring: '春', summer: '夏', autumn: '秋',
  winter: '冬', minimal: '极简', street: '街头', sweet: '甜美', formal: '正式', casual: '休闲',
  vintage: '复古', sporty: '运动', commute: '通勤', date: '约会', travel: '旅行', party: '聚会', sport: '运动',
}

const $ = (selector) => document.querySelector(selector)
const state = { imageFile: null, blobUrls: new Set(), itemsRequestId: 0, wishesRequestId: 0 }

function baseUrl() { return $('#baseUrl').value.trim().replace(/\/$/, '') }
function token() { return $('#token').value.trim() }
function fullUrl(path) { return path.startsWith('http') ? path : `${baseUrl()}${path}` }

function addLog(method, path, status, payload, ok) {
  const entry = document.createElement('article')
  entry.className = `log-entry ${ok ? 'ok' : 'bad'}`
  const requestId = payload?.requestId || '—'
  entry.innerHTML = `<div class="log-head"><span>${method} ${path}</span><span>${status} · ${requestId}</span></div>`
  const pre = document.createElement('pre')
  pre.textContent = payload == null ? '(empty response)' : JSON.stringify(payload, null, 2)
  entry.append(pre)
  $('#logList').prepend(entry)
}

async function api(path, options = {}) {
  const method = options.method || 'GET'
  const headers = new Headers(options.headers || {})
  headers.set('Authorization', `Bearer ${token()}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  try {
    const response = await fetch(fullUrl(path), { ...options, headers })
    const payload = response.status === 204 ? null : await response.json().catch(() => ({ message: '响应不是 JSON' }))
    addLog(method, path, response.status, payload, response.ok && (payload?.code ?? 0) === 0)
    if (!response.ok || (payload && payload.code !== 0)) throw new Error(payload?.message || `HTTP ${response.status}`)
    return payload?.data ?? null
  } catch (error) {
    if (!(error instanceof Error)) throw error
    if (error.message === 'Failed to fetch') addLog(method, path, 'NETWORK', { message: error.message }, false)
    throw error
  }
}

function setHealth(ok, text) {
  $('#healthDot').className = `dot ${ok ? 'ok' : 'bad'}`
  $('#healthText').textContent = text
}

function option(value, selected = false) {
  return `<option value="${value}" ${selected ? 'selected' : ''}>${labels[value] || value}</option>`
}

function fillDictionaries() {
  document.querySelectorAll('select[name="category"]').forEach((select) => {
    const initial = select.querySelector('option[value=""]')?.outerHTML || ''
    select.innerHTML = initial + dictionaries.categories.map((v, i) => option(v, !initial && i === 0)).join('')
  })
  document.querySelectorAll('select[name="season"]').forEach((select) => {
    const initial = select.querySelector('option[value=""]')?.outerHTML || ''
    select.innerHTML = initial + dictionaries.seasons.map((v) => option(v, !initial && ['spring', 'autumn'].includes(v))).join('')
  })
  document.querySelectorAll('select[name="style"]').forEach((select, index) => {
    select.innerHTML = dictionaries.styles.map((v) => option(v, index === 0 && v === 'minimal')).join('')
  })
  document.querySelectorAll('select[name="occasion"]').forEach((select, index) => {
    select.innerHTML = dictionaries.occasions.map((v) => option(v, index === 0 && v === 'casual')).join('')
  })
}

function selectedValues(select) { return [...select.selectedOptions].map((entry) => entry.value) }

async function authenticatedImage(element, path) {
  if (!path) return
  try {
    const response = await fetch(fullUrl(path), { headers: { Authorization: `Bearer ${token()}` } })
    if (!response.ok) return
    const url = URL.createObjectURL(await response.blob())
    state.blobUrls.add(url)
    const img = document.createElement('img')
    img.src = url
    img.alt = ''
    element.replaceChildren(img)
  } catch (_) { /* 图片失败不影响接口调试 */ }
}

async function checkHealth() {
  try {
    await api('/health')
    setHealth(true, '服务已连接')
  } catch (error) {
    setHealth(false, error.message)
  }
}

async function uploadImage() {
  const file = $('#imageInput').files[0]
  if (!file) return alert('请先选择图片')
  const body = new FormData()
  body.append('file', file)
  try {
    const data = await api('/api/v1/uploads/image', { method: 'POST', body })
    $('#fileId').value = data.fileId
    $('#recognizeBtn').disabled = false
    await authenticatedImage($('#localPreview'), data.thumbUrl)
  } catch (error) { alert(error.message) }
}

async function recognizeImage() {
  const imageFileId = $('#fileId').value.trim()
  if (!imageFileId) return alert('请先上传图片')
  try {
    const data = await api('/api/v1/ai/recognize', {
      method: 'POST',
      body: JSON.stringify({ imageFileId }),
    })
    alert(`识别流程完成：${data.id}，当前状态 ${data.verify_status}`)
    $('#fileId').value = ''
    $('#recognizeBtn').disabled = true
    await loadItems()
  } catch (error) {
    alert(`${error.message}\n失败记录仍会出现在衣橱列表，可在配置模型后重试。`)
    await loadItems()
  }
}

async function createManual(event) {
  event.preventDefault()
  const form = new FormData(event.currentTarget)
  const imageFileId = $('#fileId').value.trim()
  if (!imageFileId) return alert('请先上传图片或填写 fileId')
  const warmth = form.get('warmth')
  const payload = {
    name: form.get('name'), category: form.get('category'), color: form.get('color') || null,
    warmth: warmth ? Number(warmth) : null,
    season: selectedValues(event.currentTarget.elements.season),
    style: selectedValues(event.currentTarget.elements.style),
    occasion: selectedValues(event.currentTarget.elements.occasion),
    visibility: form.get('visibility'), imageFileId,
  }
  try {
    await api('/api/v1/items', { method: 'POST', body: JSON.stringify(payload) })
    $('#fileId').value = ''
    $('#recognizeBtn').disabled = true
    await loadItems()
  } catch (error) { alert(error.message) }
}

function button(text, action, id, danger = false) {
  const element = document.createElement('button')
  element.type = 'button'
  element.textContent = text
  element.dataset.action = action
  element.dataset.id = id
  if (danger) element.className = 'danger'
  return element
}

async function renderItems(items, requestId) {
  const list = $('#itemList')
  if (!items.length) {
    if (requestId !== state.itemsRequestId) return
    list.classList.add('empty')
    list.textContent = '没有符合条件的衣物'
    return
  }
  const fragment = document.createDocumentFragment()
  for (const item of items) {
    const card = $('#itemTemplate').content.firstElementChild.cloneNode(true)
    card.querySelector('h3').textContent = item.name
    const badge = card.querySelector('.badge')
    badge.textContent = item.verify_status
    badge.classList.add(item.verify_status)
    const meta = card.querySelector('.item-meta')
    if (item.category) {
      const categoryButton = button(labels[item.category] || item.category, 'filter-category', item.category)
      categoryButton.className = 'category-filter'
      categoryButton.title = `只看${labels[item.category] || item.category}`
      meta.append(categoryButton)
    } else {
      meta.append(document.createTextNode('未分类'))
    }
    meta.append(document.createTextNode([
      item.color || '未填颜色',
      item.warmth ? `保暖 ${item.warmth}` : '未填保暖度',
      item.visibility === 'public' ? '公开' : '私密',
    ].map((value) => ` · ${value}`).join('')))
    card.querySelector('.item-tags').textContent = [
      item.colors?.length ? `颜色组：${item.colors.join('、')}` : '',
      item.material ? `材质：${item.material}` : '',
      item.pattern ? `图案：${item.pattern}` : '',
      item.season?.length ? `季节：${item.season.map((value) => labels[value] || value).join('、')}` : '',
      item.style?.length ? `风格：${item.style.map((value) => labels[value] || value).join('、')}` : '',
      item.occasion?.length ? `场合：${item.occasion.map((value) => labels[value] || value).join('、')}` : '',
    ].filter(Boolean).join(' ｜ ')
    card.querySelector('.item-id').textContent = item.id
    const actions = card.querySelector('.item-actions')
    actions.append(button('编辑', 'edit', item.id))
    if (item.verify_status === 'pending') actions.append(button('确认', 'confirm', item.id))
    if (item.verify_status === 'failed') actions.append(button('重试识别', 'retry', item.id))
    actions.append(button(item.is_favorite ? '取消常用' : '标为常用', 'favorite', item.id))
    actions.append(button('删除', 'delete', item.id, true))
    await authenticatedImage(card.querySelector('.item-image'), item.thumb_url)
    if (requestId !== state.itemsRequestId) return
    fragment.append(card)
  }
  if (requestId !== state.itemsRequestId) return
  list.classList.remove('empty')
  list.replaceChildren(fragment)
}

async function loadItems(event) {
  if (event) {
    event.preventDefault()
    $('#filterForm').elements.page.value = '1'
  }
  const requestId = ++state.itemsRequestId
  const form = new FormData($('#filterForm'))
  const page = Math.max(1, Number(form.get('page') || 1))
  const pageSize = Number(form.get('pageSize') || 10)
  const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) })
  for (const key of ['category', 'season', 'color', 'keyword']) {
    if (form.get(key)) params.set(key, form.get(key))
  }
  try {
    const data = await api(`/api/v1/items?${params}`)
    if (requestId !== state.itemsRequestId) return
    const pageCount = Math.max(1, Math.ceil(data.total / pageSize))
    $('#itemSummary').textContent = `共 ${data.total} 件 · 第 ${page}/${pageCount} 页 · 当前身份 ${$('#userId').value.trim()}`
    $('#prevPage').disabled = page <= 1
    $('#nextPage').disabled = page >= pageCount
    await renderItems(data.list, requestId)
  } catch (error) { alert(error.message) }
}

async function itemAction(event) {
  const target = event.target.closest('button[data-action]')
  if (!target) return
  const { action, id } = target.dataset
  try {
    if (action === 'filter-category') {
      $('#filterForm').elements.category.value = id
      $('#filterForm').elements.page.value = '1'
      await loadItems()
      return
    } else if (action === 'delete') {
      if (!confirm(`确认删除 ${id}？历史记录只做软删除。`)) return
      await api(`/api/v1/items/${id}`, { method: 'DELETE' })
    } else if (action === 'confirm') {
      await api(`/api/v1/items/${id}/confirm`, { method: 'POST' })
    } else if (action === 'retry') {
      await api(`/api/v1/ai/retry/${id}`, { method: 'POST' })
    } else if (action === 'favorite') {
      const current = target.textContent === '取消常用'
      await api(`/api/v1/items/${id}`, { method: 'PATCH', body: JSON.stringify({ is_favorite: !current }) })
    } else if (action === 'edit') {
      const item = await api(`/api/v1/items/${id}`)
      openEditDialog(item)
      return
    }
    await loadItems()
  } catch (error) { alert(error.message) }
}

function setSelected(select, values = []) {
  const selected = new Set(values)
  for (const option of select.options) option.selected = selected.has(option.value)
}

function openEditDialog(item) {
  const form = $('#editForm')
  form.elements.itemId.value = item.id
  form.elements.name.value = item.name || ''
  form.elements.category.value = item.category || ''
  form.elements.color.value = item.color || ''
  form.elements.colors.value = (item.colors || []).join(', ')
  form.elements.warmth.value = item.warmth || ''
  form.elements.material.value = item.material || ''
  form.elements.pattern.value = item.pattern || ''
  form.elements.visibility.value = item.visibility || 'private'
  form.elements.isFavorite.checked = Boolean(item.is_favorite)
  setSelected(form.elements.season, item.season)
  setSelected(form.elements.style, item.style)
  setSelected(form.elements.occasion, item.occasion)
  $('#editDialog').showModal()
}

async function saveEdit(event) {
  event.preventDefault()
  const form = event.currentTarget
  const warmth = form.elements.warmth.value
  const payload = {
    name: form.elements.name.value,
    category: form.elements.category.value || null,
    color: form.elements.color.value.trim() || null,
    colors: form.elements.colors.value.split(/[,，]/).map((value) => value.trim()).filter(Boolean),
    warmth: warmth ? Number(warmth) : null,
    material: form.elements.material.value.trim() || null,
    pattern: form.elements.pattern.value.trim() || null,
    season: selectedValues(form.elements.season),
    style: selectedValues(form.elements.style),
    occasion: selectedValues(form.elements.occasion),
    visibility: form.elements.visibility.value,
    is_favorite: form.elements.isFavorite.checked,
  }
  try {
    await api(`/api/v1/items/${form.elements.itemId.value}`, { method: 'PATCH', body: JSON.stringify(payload) })
    $('#editDialog').close()
    await loadItems()
  } catch (error) { alert(error.message) }
}

async function addWish(event) {
  event.preventDefault()
  const form = event.currentTarget
  const sourceItemId = new FormData(form).get('sourceItemId')
  try {
    await api('/api/v1/wish-items', { method: 'POST', body: JSON.stringify({ source_item_id: sourceItemId }) })
    form.reset()
    await loadWishes()
  } catch (error) { alert(error.message) }
}

async function loadWishes() {
  const requestId = ++state.wishesRequestId
  try {
    const data = await api('/api/v1/wish-items')
    if (requestId !== state.wishesRequestId) return
    const list = $('#wishList')
    if (!data.list.length) {
      list.classList.add('empty')
      list.textContent = '心愿衣橱为空'
      return
    }
    const fragment = document.createDocumentFragment()
    for (const wish of data.list) {
      const card = $('#itemTemplate').content.firstElementChild.cloneNode(true)
      card.querySelector('h3').textContent = wish.snapshot.name
      card.querySelector('.badge').textContent = wish.available ? 'available' : 'unavailable'
      card.querySelector('.item-meta').textContent = [labels[wish.snapshot.category] || wish.snapshot.category || '未分类', wish.snapshot.color || '未填颜色'].join(' · ')
      card.querySelector('.item-id').textContent = `${wish.id} ← ${wish.source_item_id}`
      const actions = card.querySelector('.item-actions')
      if (wish.available) actions.append(button('复制到衣橱', 'copy-wish', wish.id))
      actions.append(button('取消收藏', 'delete-wish', wish.id, true))
      await authenticatedImage(card.querySelector('.item-image'), wish.snapshot.thumb_url)
      if (requestId !== state.wishesRequestId) return
      fragment.append(card)
    }
    if (requestId !== state.wishesRequestId) return
    list.classList.remove('empty')
    list.replaceChildren(fragment)
  } catch (error) { alert(error.message) }
}

async function wishAction(event) {
  const target = event.target.closest('button[data-action]')
  if (!target) return
  try {
    if (target.dataset.action === 'delete-wish') await api(`/api/v1/wish-items/${target.dataset.id}`, { method: 'DELETE' })
    if (target.dataset.action === 'copy-wish') await api(`/api/v1/wish-items/${target.dataset.id}/copy-to-wardrobe`, { method: 'POST' })
    await Promise.all([loadWishes(), loadItems()])
  } catch (error) { alert(error.message) }
}

function applyIdentity() {
  const user = $('#userId').value.trim()
  $('#token').value = `dev:${user}`
  setHealth(false, `身份已切换为 ${user}`)
  loadItems()
  loadWishes()
}

$('#healthBtn').addEventListener('click', checkHealth)
$('#applyIdentity').addEventListener('click', applyIdentity)
$('#uploadBtn').addEventListener('click', uploadImage)
$('#recognizeBtn').addEventListener('click', recognizeImage)
$('#createForm').addEventListener('submit', createManual)
$('#filterForm').addEventListener('submit', loadItems)
$('#filterForm').elements.category.addEventListener('change', loadItems)
$('#filterForm').elements.season.addEventListener('change', loadItems)
$('#filterForm').elements.pageSize.addEventListener('change', loadItems)
$('#loadItemsBtn').addEventListener('click', loadItems)
$('#prevPage').addEventListener('click', () => {
  const input = $('#filterForm').elements.page
  input.value = String(Math.max(1, Number(input.value) - 1))
  loadItems()
})
$('#nextPage').addEventListener('click', () => {
  const input = $('#filterForm').elements.page
  input.value = String(Number(input.value) + 1)
  loadItems()
})
$('#itemList').addEventListener('click', itemAction)
$('#editForm').addEventListener('submit', saveEdit)
$('#editClose').addEventListener('click', () => $('#editDialog').close())
$('#editCancel').addEventListener('click', () => $('#editDialog').close())
$('#wishForm').addEventListener('submit', addWish)
$('#loadWishesBtn').addEventListener('click', loadWishes)
$('#wishList').addEventListener('click', wishAction)
$('#clearLog').addEventListener('click', () => $('#logList').replaceChildren())
$('#imageInput').addEventListener('change', (event) => {
  const file = event.target.files[0]
  if (!file) return
  const url = URL.createObjectURL(file)
  state.blobUrls.add(url)
  $('#localPreview').innerHTML = `<img src="${url}" alt="本地图片预览" />`
})
window.addEventListener('beforeunload', () => state.blobUrls.forEach((url) => URL.revokeObjectURL(url)))

$('#baseUrl').value = window.location.origin
fillDictionaries()
checkHealth()
loadItems()
loadWishes()
