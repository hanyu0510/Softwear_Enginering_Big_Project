export const courseEnabled = import.meta.env.DEV && import.meta.env.VITE_COURSE_DEMO === '1'

export function localImage(path) {
  if (!path) return ''
  try {
    const url = new URL(path, location.href)
    if (url.origin !== location.origin || url.username || url.password) return ''
    if (!courseEnabled && url.pathname.startsWith('/__course/')) return ''
    return url.pathname + url.search
  } catch {
    return ''
  }
}
