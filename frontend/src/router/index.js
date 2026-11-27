import { createRouter, createWebHashHistory } from 'vue-router'
import { restoreSession, session } from '../api/session'

export const tabs = [
  { path: '/home', label: '首页', icon: 'home', component: () => import('../views/HomeView.vue') },
  { path: '/outfit', label: '推荐', desktopLabel: '穿搭推荐', icon: 'sparkle', component: () => import('../views/OutfitView.vue') },
  { path: '/wardrobe', label: '衣橱', desktopLabel: '我的衣橱', icon: 'hanger', component: () => import('../views/WardrobeView.vue') },
  { path: '/profile', label: '我的', icon: 'user', component: () => import('../views/ProfileView.vue') },
]

const router = createRouter({
  history: createWebHashHistory(),
  scrollBehavior: (_to, _from, saved) => saved || { top: 0 },
  routes: [
    { path: '/', redirect: '/home' },
    { path: '/login', component: () => import('../views/LoginView.vue'), meta: { account: true } },
    { path: '/register', component: () => import('../views/RegisterView.vue'), meta: { account: true } },
    { path: '/forgot-password', component: () => import('../views/ForgotPasswordView.vue'), meta: { account: true } },
    ...tabs.map(({ path, label, component }) => ({ path, component, meta: { showTabBar: true, private: true, title: label } })),
    { path: '/posts/new', component: () => import('../views/PostComposeView.vue'), meta: { private: true, title: '发布穿搭', back: '/home', returnScroll: true } },
    { path: '/posts/:id', component: () => import('../views/PostView.vue'), meta: { private: true, title: '帖子详情', back: '/home', returnScroll: true } },
    { path: '/outfit/results/:id', component: () => import('../views/OutfitResultView.vue'), meta: { private: true, title: '推荐结果', back: '/outfit' } },
    { path: '/wardrobe/new', component: () => import('../views/ItemFormView.vue'), meta: { private: true, title: '添加衣物', back: '/wardrobe' } },
    { path: '/wardrobe/items/:id', component: () => import('../views/ItemView.vue'), meta: { private: true, title: '衣物详情', back: '/wardrobe', returnScroll: true } },
    { path: '/wardrobe/items/:id/edit', component: () => import('../views/ItemFormView.vue'), meta: { private: true, title: '编辑衣物', back: route => '/wardrobe/items/' + route.params.id } },
    { path: '/wardrobe/recognition/:id', component: () => import('../views/ItemFormView.vue'), meta: { private: true, title: '确认识图建议', back: '/wardrobe' } },
    { path: '/profile/account', component: () => import('../views/AccountView.vue'), meta: { private: true, title: '账号管理', back: '/profile' } },
    { path: '/profile/:section', component: () => import('../views/ProfileSectionView.vue'), meta: { private: true, title: '个人记录', back: '/profile' } },
    { path: '/:pathMatch(.*)*', redirect: '/home' },
  ],
})

router.beforeEach(async to => {
  await restoreSession()
  if (to.meta.private && !session.token) return { path: '/login', query: { next: to.fullPath } }
  if (to.path === '/login' && session.token) return '/home'
  return true
})

export default router
