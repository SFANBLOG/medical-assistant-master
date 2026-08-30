import client from './client'
import type {
    AdminUserRow,
    Appointment,
    Bill,
    Conversation,
    ConversationDetail,
    DashboardStats,
    DocumentItem,
    Hospitalization,
    KnowledgeBase,
    NursingRecord,
    PatientSummary,
    RecentConversation,
    Role,
    Schedule,
    SearchHit,
    User,
    Visibility,
} from '@/types'

export const authApi = {
  login: (username: string, password: string) =>
    client.post<{ token: string; user: User }>('/auth/login', { username, password }).then((r) => r.data),
  register: (username: string, password: string, role: Role, display_name?: string) =>
    client
      .post<{ token: string; user: User }>('/auth/register', {
        username,
        password,
        role,
        display_name,
      })
      .then((r) => r.data),
  me: () => client.get<{ user: User }>('/auth/me').then((r) => r.data.user),
}

export const kbApi = {
  list: () => client.get<{ items: KnowledgeBase[] }>('/kb').then((r) => r.data.items),
  create: (data: { name: string; description?: string; visibility?: string }) =>
    client.post<KnowledgeBase>('/kb', data).then((r) => r.data),
  remove: (kbId: number) => client.delete(`/kb/${kbId}`).then((r) => r.data),
  documents: (kbId: number) =>
    client.get<{ items: DocumentItem[] }>(`/kb/${kbId}/documents`).then((r) => r.data.items),
  uploadDoc: (kbId: number, file: File, visibility?: Visibility) => {
    const form = new FormData()
    form.append('file', file)
    if (visibility) form.append('visibility', visibility)
    return client.post<DocumentItem>(`/kb/${kbId}/documents`, form).then((r) => r.data)
  },
  deleteDoc: (kbId: number, docId: number) =>
    client.delete(`/kb/${kbId}/documents/${docId}`).then((r) => r.data),
  search: (kbId: number, q: string, k = 5) =>
    client.get<{ items: SearchHit[] }>(`/kb/${kbId}/search`, { params: { q, k } }).then((r) => r.data.items),
}

export const chatApi = {
  conversations: (params: { q?: string; page?: number; page_size?: number }) =>
    client
      .get<{ total: number; items: Conversation[] }>('/chat/conversations', { params })
      .then((r) => r.data),
  detail: (id: string) =>
    client.get<ConversationDetail>(`/chat/conversations/${id}`).then((r) => r.data),
  remove: (id: string) => client.delete(`/chat/conversations/${id}`).then((r) => r.data),
}

export const dashboardApi = {
  stats: () => client.get<DashboardStats>('/dashboard/stats').then((r) => r.data),
  recent: () =>
    client.get<{ items: RecentConversation[] }>('/dashboard/recent').then((r) => r.data.items),
}

export const patientApi = {
  hospitalizations: () =>
    client.get<{ items: Hospitalization[] }>('/patient/hospitalizations').then((r) => r.data.items),
  bills: (params?: { category?: string; status?: string }) =>
    client.get<{ items: Bill[] }>('/patient/bills', { params }).then((r) => r.data.items),
  doctors: () =>
    client
      .get<{ items: { id: number; username: string; display_name: string }[] }>('/patient/doctors')
      .then((r) => r.data.items),
  appointments: () =>
    client.get<{ items: Appointment[] }>('/patient/appointments').then((r) => r.data.items),
  createAppointment: (data: {
    department: string
    date: string
    time_slot: string
    doctor_id?: number
    symptom?: string
  }) => client.post<Appointment>('/patient/appointments', data).then((r) => r.data),
  cancelAppointment: (id: number) =>
    client.post(`/patient/appointments/${id}/cancel`).then((r) => r.data),
}

export const doctorApi = {
  patients: (params?: { q?: string; page?: number; page_size?: number }) =>
    client
      .get<{ total: number; items: PatientSummary[] }>('/doctor/patients', { params })
      .then((r) => r.data),
  patientHospitalizations: (patientId: number) =>
    client
      .get<{ items: Hospitalization[] }>(`/doctor/patients/${patientId}/hospitalizations`)
      .then((r) => r.data.items),
  hospitalizations: (params?: { status?: string; q?: string }) =>
    client
      .get<{ items: Hospitalization[] }>('/doctor/hospitalizations', { params })
      .then((r) => r.data.items),
  createHospitalization: (data: {
    patient_id: number
    department: string
    admit_date: string
    diagnosis?: string
    ward?: string
    bed_no?: string
  }) => client.post<Hospitalization>('/doctor/hospitalizations', data).then((r) => r.data),
  updateHospitalization: (
    id: number,
    data: { status?: string; discharge_date?: string; diagnosis?: string; total_cost?: number },
  ) => client.put<Hospitalization>(`/doctor/hospitalizations/${id}`, data).then((r) => r.data),
}

export const nurseApi = {
  patients: (q?: string) =>
    client.get<{ items: PatientSummary[] }>('/nurse/patients', { params: { q } }).then((r) => r.data.items),
  nursingRecords: (patientId?: number) =>
    client
      .get<{ items: NursingRecord[] }>('/nurse/nursing-records', { params: { patient_id: patientId } })
      .then((r) => r.data.items),
  createNursingRecord: (data: { patient_id: number; content: string; record_type?: string }) =>
    client.post<NursingRecord>('/nurse/nursing-records', data).then((r) => r.data),
}

export const scheduleApi = {
  list: (params?: { staff_id?: number; department?: string }) =>
    client.get<{ items: Schedule[] }>('/schedule', { params }).then((r) => r.data.items),
  create: (data: { staff_id?: number; work_date: string; shift?: string; department?: string; remark?: string }) =>
    client.post<Schedule>('/schedule', data).then((r) => r.data),
}

export const adminApi = {
  users: (params?: { role?: string; q?: string; page?: number; page_size?: number }) =>
    client.get<{ total: number; items: AdminUserRow[] }>('/admin/users', { params }).then((r) => r.data),
  createUser: (data: { username: string; password: string; role: Role; display_name?: string }) =>
    client.post<AdminUserRow>('/admin/users', data).then((r) => r.data),
  updateUser: (id: number, data: { role?: string; display_name?: string; reset_password?: string }) =>
    client.put<AdminUserRow>(`/admin/users/${id}`, data).then((r) => r.data),
  removeUser: (id: number) => client.delete(`/admin/users/${id}`).then((r) => r.data),
  stats: () => client.get('/admin/stats').then((r) => r.data),
}
