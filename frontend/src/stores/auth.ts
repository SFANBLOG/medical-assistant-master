import {defineStore} from 'pinia'
import {authApi} from '../api/endpoints'
import type {Role, User} from '../types'

function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem('mia_user')
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

interface AuthState {
  token: string | null
  user: User | null
}

export const useAuth = defineStore('auth', {
  state: (): AuthState => ({
    token: localStorage.getItem('mia_token'),
    user: readStoredUser(),
  }),
  actions: {
    async login(username: string, password: string) {
      const { token, user } = await authApi.login(username, password)
      localStorage.setItem('mia_token', token)
      localStorage.setItem('mia_user', JSON.stringify(user))
      this.token = token
      this.user = user
    },
    async register(username: string, password: string, role: Role, displayName?: string) {
      const { token, user } = await authApi.register(username, password, role, displayName)
      localStorage.setItem('mia_token', token)
      localStorage.setItem('mia_user', JSON.stringify(user))
      this.token = token
      this.user = user
    },
    async fetchMe() {
      const user = await authApi.me()
      localStorage.setItem('mia_user', JSON.stringify(user))
      this.user = user
    },
    logout() {
      localStorage.removeItem('mia_token')
      localStorage.removeItem('mia_user')
      this.token = null
      this.user = null
    },
  },
})
