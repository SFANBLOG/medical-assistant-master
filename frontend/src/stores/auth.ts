import { create } from 'zustand'
import type { User } from '../types'
import { authApi } from '../api/endpoints'

interface AuthState {
  token: string | null
  user: User | null
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string, role: User['role'], displayName?: string) => Promise<void>
  fetchMe: () => Promise<void>
  logout: () => void
}

function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem('mia_user')
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

export const useAuth = create<AuthState>((set) => ({
  token: localStorage.getItem('mia_token'),
  user: readStoredUser(),
  async login(username, password) {
    const { token, user } = await authApi.login(username, password)
    localStorage.setItem('mia_token', token)
    localStorage.setItem('mia_user', JSON.stringify(user))
    set({ token, user })
  },
  async register(username, password, role, displayName) {
    const { token, user } = await authApi.register(username, password, role, displayName)
    localStorage.setItem('mia_token', token)
    localStorage.setItem('mia_user', JSON.stringify(user))
    set({ token, user })
  },
  async fetchMe() {
    const user = await authApi.me()
    localStorage.setItem('mia_user', JSON.stringify(user))
    set({ user })
  },
  logout() {
    localStorage.removeItem('mia_token')
    localStorage.removeItem('mia_user')
    set({ token: null, user: null })
  },
}))
