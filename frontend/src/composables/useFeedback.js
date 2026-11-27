import { ref } from 'vue'

export const feedback = ref('')
let timer

export function notify(message) {
  clearTimeout(timer)
  feedback.value = message
  timer = setTimeout(() => { feedback.value = '' }, 2200)
}
