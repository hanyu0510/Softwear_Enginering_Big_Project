import { createRouter, createWebHashHistory } from 'vue-router'

import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import ForgotPasswordView from '../views/ForgotPasswordView.vue'
import HomeView from '../views/HomeView.vue'
import OutfitView from '../views/OutfitView.vue'
import WardrobeView from '../views/WardrobeView.vue'
import ProfileView from '../views/ProfileView.vue'

export const tabs = [
  { path: '/home', label: '首页', component: HomeView },
  { path: '/outfit', label: '穿搭', component: OutfitView },
  { path: '/wardrobe', label: '衣橱', component: WardrobeView },
  { path: '/profile', label: '我的', component: ProfileView },
]

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', component: LoginView },
    { path: '/register', component: RegisterView },
    { path: '/forgot-password', component: ForgotPasswordView },
    ...tabs.map(({ path, component }) => ({
      path,
      component,
      meta: { showTabBar: true },
    })),
  ],
})
