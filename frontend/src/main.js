import { createApp } from 'vue'
import TDesign from 'tdesign-mobile-vue'
import 'tdesign-mobile-vue/dist/tdesign.css'

import App from './App.vue'
import router from './router/index.js'

createApp(App).use(router).use(TDesign).mount('#app')
