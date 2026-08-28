/**
 * Axios 实例 + 拦截器 + 全部后端 API 封装
 *
 * - 请求拦截器自动附加 Authorization: Bearer <token>
 * - 响应拦截器直接返回 data；401 自动清理登录态并跳转登录页
 * - SSE 流式聊天使用原生 fetch（需要手动带 token 头）
 */
import axios, { type AxiosInstance, type AxiosError } from 'axios'
import type {
  AuthResult,
  User,
  Paged,
  KnowledgeBase,
  DocumentItem,
  Conversation,
  Message,
  Hospitalization,
  Bill,
  Appointment,
  NursingRecord,
  Schedule,
  SystemOverview,
  UserStats,
  KbStats,
  BusinessStats,
  ChatStats,
  RevenueStats,
  DeptDistItem,
  BillCategoryItem,
  Role,
} from '@/types'

/* ======================= Axios 实例 ======================= */
export const http: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 请求拦截器：附加 token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('medical_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：直接返回 data；统一错误处理
http.interceptors.response.use(
  (resp) => resp.data,
  (error: AxiosError) => {
    const status = error.response?.status
    if (status === 401) {
      localStorage.removeItem('medical_token')
      localStorage.removeItem('medical_user')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    const data = error.response?.data as Record<string, unknown> | undefined
    const msg =
      (data && (data.error as string)) ||
      (data && (data.message as string)) ||
      error.message ||
      '请求失败'
    return Promise.reject(new Error(msg))
  },
)

/* ======================= 通用请求函数 ======================= */
function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  return http.get(url, { params }) as Promise<T>
}

function post<T>(url: string, data?: unknown): Promise<T> {
  return http.post(url, data) as Promise<T>
}

function put<T>(url: string, data?: unknown): Promise<T> {
  return http.put(url, data) as Promise<T>
}

function del<T>(url: string): Promise<T> {
  return http.delete(url) as Promise<T>
}

/* ======================= 认证 ======================= */
export const authApi = {
  login: (data: { username: string; password: string }) =>
    post<AuthResult>('/auth/login', data),
  register: (data: {
    username: string
    password: string
    role: 'patient' | 'public'
    display_name: string
  }) => post<AuthResult>('/auth/register', data),
  me: () => get<User>('/auth/me'),
  listUsers: (params: { page?: number; size?: number; role?: string }) =>
    get<Paged<User>>('/auth/users', params),
  createUser: (data: {
    username: string
    password: string
    role: Role
    display_name: string
  }) => post<User>('/auth/users', data),
  updateUser: (
    id: number,
    data: { display_name?: string; role?: Role; password?: string },
  ) => put<User>(`/auth/users/${id}`, data),
  deleteUser: (id: number) => del<{ message: string }>(`/auth/users/${id}`),
}

/* ======================= 聊天 ======================= */
export const chatApi = {
  listConversations: () => get<Conversation[]>('/chat/conversations'),
  createConversation: (data: { kb_id?: number | null; title: string }) =>
    post<Conversation>('/chat/conversations', data),
  getConversation: (id: string) =>
    get<Conversation & { messages: Message[] }>(`/chat/conversations/${id}`),
  deleteConversation: (id: string) =>
    del<{ message: string }>(`/chat/conversations/${id}`),
  getHistory: (params: { limit?: number } = { limit: 50 }) =>
    get<Message[]>('/chat/history', params),
}

/** SSE 流式聊天 URL（配合 authHeaders 使用原生 fetch） */
export function chatStreamUrl(convId: string): string {
  return `/api/chat/stream/${convId}`
}

/** 原生 fetch 所需的认证请求头 */
export function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('medical_token') || ''
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  }
}

/* ======================= 知识库 ======================= */
export const kbApi = {
  listKb: (params: { page?: number; size?: number }) =>
    get<Paged<KnowledgeBase>>('/kb/', params),
  createKb: (data: {
    name: string
    description: string
    visibility: 'public' | 'private'
  }) => post<KnowledgeBase>('/kb/', data),
  deleteKb: (id: number) => del<{ message: string }>(`/kb/${id}`),
  listDocuments: (kbId: number, params: { page?: number; size?: number }) =>
    get<Paged<DocumentItem>>(`/kb/${kbId}/documents`, params),
  uploadDocument: (kbId: number, formData: FormData) =>
    post<{ doc_id: number; filename: string; chunk_count: number; status: string }>(
      `/kb/${kbId}/documents`,
      formData,
    ),
  deleteDocument: (docId: number) =>
    del<{ message: string }>(`/kb/documents/${docId}`),
}

/* ======================= 医疗业务 ======================= */
export const medicalApi = {
  // 住院信息
  listHospitalizations: (params: {
    page?: number
    size?: number
    patient_id?: number
  }) => get<Paged<Hospitalization>>('/medical/hospitalizations', params),
  createHospitalization: (data: Partial<Hospitalization>) =>
    post<Hospitalization>('/medical/hospitalizations', data),
  updateHospitalization: (id: number, data: Partial<Hospitalization>) =>
    put<Hospitalization>(`/medical/hospitalizations/${id}`, data),

  // 消费明细
  listBills: (params: { page?: number; size?: number; patient_id?: number }) =>
    get<Paged<Bill>>('/medical/bills', params),

  // 预约挂号
  listAppointments: (params: {
    page?: number
    size?: number
    patient_id?: number
  }) => get<Paged<Appointment>>('/medical/appointments', params),
  createAppointment: (data: Partial<Appointment>) =>
    post<Appointment>('/medical/appointments', data),
  updateAppointment: (id: number, data: Partial<Appointment>) =>
    put<Appointment>(`/medical/appointments/${id}`, data),

  // 护理记录
  listNursingRecords: (params: {
    page?: number
    size?: number
    patient_id?: number
  }) => get<Paged<NursingRecord>>('/medical/nursing-records', params),
  createNursingRecord: (data: Partial<NursingRecord>) =>
    post<NursingRecord>('/medical/nursing-records', data),

  // 排班
  listSchedules: (params: {
    page?: number
    size?: number
    staff_id?: number
  }) => get<Paged<Schedule>>('/medical/schedules', params),
  createSchedule: (data: Partial<Schedule>) =>
    post<Schedule>('/medical/schedules', data),
}

/* ======================= 仪表盘 ======================= */
export const dashboardApi = {
  overview: () => get<SystemOverview>('/dashboard/overview'),
  users: () => get<UserStats>('/dashboard/users'),
  knowledgeBases: () => get<KbStats>('/dashboard/knowledge-bases'),
  business: () => get<BusinessStats>('/dashboard/business'),
  chat: () => get<ChatStats>('/dashboard/chat'),
  revenue: () => get<RevenueStats>('/dashboard/revenue'),
  departmentDistribution: () =>
    get<DeptDistItem[]>('/dashboard/department-distribution'),
  billCategoryDistribution: () =>
    get<BillCategoryItem[]>('/dashboard/bill-category-distribution'),
}

/* ======================= 角色相关辅助函数 ======================= */

/** 角色中文名 */
export const ROLE_LABELS: Record<string, string> = {
  patient: '患者',
  doctor: '医生',
  nurse: '护士',
  public: '群众',
  admin: '管理员',
}

/**
 * 获取患者下拉选项。
 * admin 可直接读取用户表；医生/护士通过住院记录推导已知患者。
 */
export async function getPatientOptions(
  role: string,
): Promise<{ id: number; name: string }[]> {
  if (role === 'admin') {
    try {
      const res = await authApi.listUsers({ role: 'patient', size: 1000 })
      return (res.list || []).map((u) => ({
        id: u.id,
        name: u.display_name || u.username,
      }))
    } catch {
      /* 忽略，走兜底 */
    }
  }
  try {
    const res = await medicalApi.listHospitalizations({ size: 1000 })
    const map = new Map<number, string>()
    for (const h of res.list || []) {
      if (h.patient_id && !map.has(h.patient_id)) {
        map.set(h.patient_id, h.patient_name || `患者#${h.patient_id}`)
      }
    }
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }))
  } catch {
    return []
  }
}

/**
 * 获取医生下拉选项。
 * admin 读取用户表；医生默认自己。
 */
export async function getDoctorOptions(
  role: string,
  currentUserId?: number,
  currentName?: string,
): Promise<{ id: number; name: string }[]> {
  if (role === 'admin') {
    try {
      const res = await authApi.listUsers({ role: 'doctor', size: 1000 })
      return (res.list || []).map((u) => ({
        id: u.id,
        name: u.display_name || u.username,
      }))
    } catch {
      /* 忽略 */
    }
  }
  if (currentUserId) {
    return [{ id: currentUserId, name: currentName || `医生#${currentUserId}` }]
  }
  return []
}
