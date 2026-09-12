/**
 * 路由定义 + 角色守卫
 */
import type {RouteRecordRaw} from 'vue-router'
import {createRouter, createWebHashHistory} from 'vue-router'
import {useAuthStore} from '@/stores/auth'
import MainLayout from '@/layouts/MainLayout.vue'

declare module 'vue-router' {
  interface RouteMeta {
    /** 页面标题 */
    title?: string
    /** 允许访问的角色，缺省表示所有登录用户 */
    roles?: string[]
    /** 公开页面（无需登录） */
    public?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '数据仪表盘' },
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/Chat.vue'),
        meta: { title: '智能咨询' },
      },
      {
        path: 'chat/history',
        name: 'ChatHistory',
        component: () => import('@/views/ChatHistory.vue'),
        meta: { title: '咨询历史' },
      },
      {
        path: 'health-records',
        name: 'HealthRecord',
        component: () => import('@/views/HealthRecord.vue'),
        meta: { title: '健康档案' },
      },
      {
        path: 'appointment',
        name: 'Appointment',
        component: () => import('@/views/Appointment.vue'),
        meta: { title: '预约挂号' },
      },
      {
        path: 'health-info',
        name: 'HealthInfo',
        component: () => import('@/views/HealthInfo.vue'),
        meta: { title: '健康资讯' },
      },
      {
        path: 'guide',
        name: 'Guide',
        component: () => import('@/views/Guide.vue'),
        meta: { title: '就诊指南' },
      },
      {
        path: 'doctor/patients',
        name: 'PatientManage',
        component: () => import('@/views/PatientManage.vue'),
        meta: { title: '患者管理', roles: ['doctor', 'admin'] },
      },
      {
        path: 'doctor/hospitalization',
        name: 'Hospitalization',
        component: () => import('@/views/Hospitalization.vue'),
        meta: { title: '住院信息管理', roles: ['doctor', 'admin'] },
      },
      {
        path: 'doctor/schedules',
        name: 'Schedule',
        component: () => import('@/views/Schedule.vue'),
        meta: { title: '排班管理', roles: ['doctor', 'admin'] },
      },
      {
        path: 'kb',
        name: 'KnowledgeBase',
        component: () => import('@/views/KnowledgeBase.vue'),
        meta: { title: '知识库管理', roles: ['doctor', 'admin'] },
      },
      {
        path: 'nurse',
        name: 'NursingWorkbench',
        component: () => import('@/views/NursingWorkbench.vue'),
        meta: { title: '护理工作台', roles: ['nurse'] },
      },
      {
        path: 'admin/users',
        name: 'UserManage',
        component: () => import('@/views/UserManage.vue'),
        meta: { title: '系统用户管理', roles: ['admin'] },
      },
      {
        path: 'admin/system',
        name: 'SystemDashboard',
        component: () => import('@/views/SystemDashboard.vue'),
        meta: { title: '全系统数据看板', roles: ['admin'] },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  // hash 模式：PocketBay 等 PaaS 静态托管无 history fallback，
  // history 模式刷新深链（如 /login、/dashboard）会 404，hash 模式不依赖服务端。
  history: createWebHashHistory(),
  routes,
})

/**
 * 全局前置守卫：
 * 1. 未登录访问受保护页面 → /login
 * 2. 已登录访问 /login → 角色默认页
 * 3. 无权限角色访问受限页面 → 角色默认页
 */
router.beforeEach((to) => {
  const auth = useAuthStore()

  if (to.meta.public) {
    if (auth.isLoggedIn && to.path === '/login') {
      return auth.defaultRoute
    }
    document.title = to.meta.title ? `${to.meta.title} · 医智助手` : '医智助手'
    return true
  }

  if (!auth.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (to.meta.roles && !auth.canAccess(to.meta.roles)) {
    return auth.defaultRoute
  }

  document.title = to.meta.title ? `${to.meta.title} · 医智助手` : '医智助手'
  return true
})

export default router
