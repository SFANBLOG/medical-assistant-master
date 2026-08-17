import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('mia_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status = error?.response?.status
    const data = error?.response?.data
    if (status === 401) {
      localStorage.removeItem('mia_token')
      localStorage.removeItem('mia_user')
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    const message = data?.error || error?.message || '请求失败'
    return Promise.reject(new Error(message))
  },
)

export default client
