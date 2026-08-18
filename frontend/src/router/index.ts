import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores/auth'
import type { Role } from '../types'
import MainLayout from '../layouts/MainLayout.vue'

const ALL: Role[] = ['patient', 'doctor', 'nurse', 'public', 'admin']

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('../pages/LoginPage.vue'), meta: { public: true } },
    { path: '/register', component: () => import('../pages/RegisterPage.vue'), meta: { public: true } },
    {
      path: '/',
      component: MainLayout,
      children: [
        { path: '', component: () => import('../pages/DashboardPage.vue'), meta: { roles: ALL } },
        { path: 'chat', component: () => import('../pages/ChatPage.vue'), meta: { roles: ALL } },
        { path: 'chat/history', component: () => import('../pages/ChatHistoryPage.vue'), meta: { roles: ALL } },
        { path: 'chat/history/:id', component: () => import('../pages/ChatTranscriptPage.vue'), meta: { roles: ALL } },
        { path: 'health', component: () => import('../pages/HealthInfoPage.vue'), meta: { roles: ALL } },
        { path: 'guide', component: () => import('../pages/VisitGuidePage.vue'), meta: { roles: ALL } },
        { path: 'kb', component: () => import('../pages/KbManagePage.vue'), meta: { roles: ['doctor', 'admin'] } },
        { path: 'patient', component: () => import('../pages/PatientRecordsPage.vue'), meta: { roles: ['patient'] } },
        { path: 'appointments', component: () => import('../pages/AppointmentsPage.vue'), meta: { roles: ['patient', 'public'] } },
        { path: 'doctor', component: () => import('../pages/DoctorWorkbenchPage.vue'), meta: { roles: ['doctor'] } },
        { path: 'doctor/patients', component: () => import('../pages/PatientManagePage.vue'), meta: { roles: ['doctor'] } },
        { path: 'doctor/hospitalizations', component: () => import('../pages/HospitalManagePage.vue'), meta: { roles: ['doctor'] } },
        { path: 'schedule', component: () => import('../pages/SchedulePage.vue'), meta: { roles: ['doctor', 'nurse'] } },
        { path: 'nurse', component: () => import('../pages/NurseWorkbenchPage.vue'), meta: { roles: ['nurse'] } },
        { path: 'admin', component: () => import('../pages/AdminManagePage.vue'), meta: { roles: ['admin'] } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const auth = useAuth()
  if (to.meta.public) return true
  if (!auth.token || !auth.user) return { path: '/login' }
  const roles = to.meta.roles as Role[] | undefined
  if (roles && !roles.includes(auth.user.role)) return { path: '/' }
  return true
})

export { router }
