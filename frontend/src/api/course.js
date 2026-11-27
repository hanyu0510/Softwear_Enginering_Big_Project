import { reactive, watch } from 'vue'
import { send, query } from './http'
import { session } from './session'

const base = '/__course/reco'
const blank = () => ({ sceneText:'', styleText:'', destination:null, travel:false, travelDate:'' })
export const courseDraft = reactive(blank())
watch(() => session.viewerVersion, () => Object.assign(courseDraft, blank()))

export function courseRequest(path, options = {}) {
  return send(base + path, { ...options, credentials:'omit' })
}
export const cities = (keyword, signal) => courseRequest('/cities' + query({keyword}), {signal})
export const weather = (cityId, date, signal) => courseRequest('/weather' + query({cityId,date}), {signal})
export const createRecommendation = (body, signal) => courseRequest('/recommendations', {method:'POST',body,signal})
export const readRecommendation = (id, signal) => courseRequest('/recommendations/' + encodeURIComponent(id), {signal})

export function chinaDate(offset = 0) {
  const now = new Date(Date.now() + offset * 86400000)
  const parts = new Intl.DateTimeFormat('en', {timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now)
  const value = type => parts.find(part => part.type === type).value
  return [value('year'),value('month'),value('day')].join('-')
}

export function illustration(item) {
  if (item.illustration) return '/__course/media/' + item.illustration + '.webp'
  if (item.source === 'wish') return '/__course/media/khaki-trench.webp'
  const match = item.imageUrl?.match(/^\/mock\/mock_u[12]\/(\d+)\.jpg$/)
  if (!match) return ''
  // The stand-alone service ships clothing identifiers without actual photo routes.
  const files = ['cream-knit','blue-jeans','khaki-trench','floral-dress','white-sneakers','brown-bag','burgundy-scarf']
  const image = files[(Number(match[1]) - 1) % files.length]
  return image ? '/__course/media/' + image + '.webp' : ''
}

const categoryNames = { tops:'上装', bottoms:'下装', outerwear:'外套', dress:'连衣裙／套装', shoes:'鞋履', bag:'包袋', accessory:'配饰', other:'单品' }
const sampleName = /^模拟([a-z]+)(\d+)$/

export function displayName(item) {
  // Snapshot responses omit category; synthetic names carry the original catalog category and number.
  const match = item.name?.match(sampleName)
  if (!match) return item.name || '未命名单品'
  return `${categoryNames[item.category || match[1]] || '单品'} · 样本 ${match[2]}`
}

export function displayReason(result) {
  const names = new Map(result.items.map(item => [item.name, displayName(item)]))
  return result.reason?.replace(/模拟[a-z]+\d+/g, name => names.get(name) || name)
}

export const backupResult = {
  id:'backup',
  items: [
    { id:'backup-coat', name:'卡其风衣', illustration:'khaki-trench', source:'owned' },
    { id:'backup-knit', name:'奶油针织', illustration:'cream-knit', source:'owned' },
    { id:'backup-denim', name:'直筒牛仔', illustration:'blue-jeans', source:'owned' },
    { id:'backup-shoes', name:'白色运动鞋', illustration:'white-sneakers', source:'owned' },
  ],
  reason:'以卡其色外套搭配奶油针织和直筒牛仔，轻便鞋履适合步行。',
  parsed:{style_note:'示例以暖中性色叠穿组合。'},
  warnings:['备用样例为预先准备的静态内容。'],
}
