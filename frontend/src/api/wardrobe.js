import { session } from './session'

export const itemPath = id => '/items/' + encodeURIComponent(id)

export function labelFor(key, value) {
  return session.dictionary?.[key]?.find(entry => entry.value === value)?.label || value || '未设置'
}

export async function prepareImage(file) {
  const formats = ['image/jpeg', 'image/png', 'image/webp']
  if (!formats.includes(file.type)) throw new Error('请选择 JPEG、PNG 或 WebP 图片')
  if (file.size > 30 * 1024 * 1024) throw new Error('请选择 30 MB 以内的原图')
  const bitmap = await createImageBitmap(file).catch(() => { throw new Error('无法读取这张图片，请重新选择') })
  try {
    const scale = Math.min(1, 1400 / Math.max(bitmap.width, bitmap.height))
    if (scale === 1 && file.size < 700 * 1024) return file
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(bitmap.width * scale))
    canvas.height = Math.max(1, Math.round(bitmap.height * scale))
    const drawing = canvas.getContext('2d', { alpha: false })
    drawing.fillStyle = '#fff'
    drawing.fillRect(0, 0, canvas.width, canvas.height)
    drawing.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85))
    if (!blob || blob.size > 10 * 1024 * 1024) throw new Error('压缩后图片仍过大，请换一张照片')
    return new File([blob], 'garment.jpg', { type: 'image/jpeg' })
  } finally { bitmap.close() }
}
