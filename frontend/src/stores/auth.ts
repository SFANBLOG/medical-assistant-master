/**
 * 认证状态管理：token、用户信息、角色权限
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, Role } from '@/types'
import { authApi } from '@/api'

const TOKEN_KEY = 'medical_token'
const USER_KEY = 'medical_user'

export const useAuthStore = defineStore('auth', () => {
  // 从 localStorage 恢复登录态（刷新页面不丢失）
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref<User | null>(
    JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  )

  const isLoggedIn = computed(() => !!token.value)
  const role = computed<Role | ''>(() => user.value?.role || '')

  const roleLabel = computed(() => {
    const map: Record<string, string> = {
      patient: '患者',
      doctor: '医生',
      nurse: '护士',
      public: '群众',
      admin: '管理员',
    }
    return user.value ? map[user.value.role] || user.value.role : ''
  })

  /** 各角色登录后的默认落地页 */
  const defaultRoute = computed(() => {
    switch (user.value?.role) {
      case 'admin':
        return '/admin/system'
      case 'doctor':
        return '/doctor/hospitalization'
      case 'nurse':
        return '/nurse'
      default:
        return '/chat'
    }
  })

  function persist() {
    localStorage.setItem(TOKEN_KEY, token.value)
    localStorage.setItem(USER_KEY, JSON.stringify(user.value))
  }

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password })
    token.value = res.token
    user.value = res.user
    persist()
  }

  async function register(payload: {
    username: string
    password: string
    role: 'patient' | 'public'
    display_name: string
  }) {
    const res = await authApi.register(payload)
    token.value = res.token
    user.value = res.user
    persist()
  }

  /** 刷新用户信息（会话恢复） */
  async function fetchMe() {
    const me = await authApi.me()
    user.value = me
    persist()
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  /** 角色是否允许访问 */
  function canAccess(roles?: string[]): boolean {
    if (!roles || roles.length === 0) return true
    return !!user.value && roles.includes(user.value.role)
  }

  return {
    token,
    user,
    isLoggedIn,
    role,
    roleLabel,
    defaultRoute,
    login,
    register,
    fetchMe,
    logout,
    canAccess,
  }
})
