export type Role = 'patient' | 'doctor' | 'nurse' | 'public' | 'admin'

export interface User {
  id: number
  username: string
  role: Role
  display_name: string
  created_at?: string
}

export interface KnowledgeBase {
  id: number
  name: string
  description: string
  visibility: 'private' | 'public'
  owner_id: number | null
  owner_name?: string
  created_at: string
  doc_count?: number
  chunk_count?: number
}

export interface DocumentItem {
  id: number
  kb_id: number
  filename: string
  file_type: string
  chunk_count: number
  status: 'processing' | 'ready' | 'failed'
  error?: string
  created_at: string
}

export interface Citation {
  document_id: number
  chunk_index: number
  source_text: string
  title: string
  similarity: number
}

export interface Message {
  id: number
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  citations: Citation[]
}

export interface Conversation {
  id: string
  title: string
  kb_id: number | null
  kb_name?: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface ConversationDetail {
  conversation: Conversation
  messages: Message[]
}

export interface SearchHit {
  text: string
  filename: string
  chunk_index: number
  similarity: number
  score: number
}

export interface DashboardStats {
  kb_count: number
  doc_count: number
  chunk_count: number
  conversation_count: number
  message_count: number
  docs_by_kb: { name: string; doc_count: number }[]
  role_breakdown?: { role: string; count: number }[]
  role: Role
}

export interface RecentConversation {
  id: string
  title: string
  created_at: string
  username: string
  role: Role
  kb_name?: string
}

export const ROLE_LABELS: Record<Role, string> = {
  patient: '患者',
  doctor: '医生',
  nurse: '护士',
  public: '群众',
  admin: '管理员',
}

export const ROLE_COLORS: Record<Role, string> = {
  patient: 'blue',
  doctor: 'volcano',
  nurse: 'purple',
  public: 'green',
  admin: 'magenta',
}

// ===== 患者健康档案 / 医护业务类型 =====

export type HospitalizationStatus = 'in_hospital' | 'discharged'

export interface Hospitalization {
  id: number
  patient_id: number
  admit_date: string
  discharge_date?: string | null
  department: string
  ward?: string
  bed_no?: string
  diagnosis?: string
  doctor_id?: number | null
  doctor_name?: string
  patient_name?: string
  patient_username?: string
  status: HospitalizationStatus
  total_cost: number
  created_at?: string
}

export type BillStatus = 'paid' | 'unpaid'

export interface Bill {
  id: number
  patient_id: number
  bill_no: string
  category: string
  description?: string
  amount: number
  status: BillStatus
  created_at: string
}

export type AppointmentStatus = 'booked' | 'confirmed' | 'visited' | 'cancelled'

export interface Appointment {
  id: number
  patient_id: number
  doctor_id?: number | null
  doctor_name?: string
  department: string
  date: string
  time_slot: string
  symptom?: string
  fee: number
  status: AppointmentStatus
  created_at?: string
}

export type NursingRecordType = 'daily' | 'medication' | 'vitals' | 'other'

export interface NursingRecord {
  id: number
  patient_id: number
  patient_name?: string
  nurse_id?: number | null
  nurse_name?: string
  record_type: NursingRecordType
  content: string
  recorded_at: string
}

export type Shift = 'day' | 'night' | 'evening' | 'off'

export interface Schedule {
  id: number
  staff_id: number
  staff_name?: string
  staff_role?: Role
  work_date: string
  shift: Shift
  department?: string
  remark?: string
  status?: string
}

export interface PatientSummary {
  id: number
  username: string
  display_name: string
  created_at?: string
  latest_admission?: Hospitalization | null
  current_status?: string
  current_department?: string
  current_bed?: string
}

export interface AdminUserRow {
  id: number
  username: string
  role: Role
  display_name: string
  created_at: string
}

export const SHIFT_LABELS: Record<Shift, string> = {
  day: '白班',
  night: '夜班',
  evening: '中班',
  off: '休息',
}

export const APPOINTMENT_STATUS_LABELS: Record<AppointmentStatus, string> = {
  booked: '已预约',
  confirmed: '已确认',
  visited: '已就诊',
  cancelled: '已取消',
}
