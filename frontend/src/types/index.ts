/** 系统角色 */
export type Role = 'patient' | 'doctor' | 'nurse' | 'public' | 'admin'

/** 用户 */
export interface User {
  id: number
  username: string
  role: Role
  display_name?: string
  created_at?: string
}

/** 登录/注册结果 */
export interface AuthResult {
  token: string
  user: User
}

/** 分页响应 */
export interface Paged<T> {
  total: number
  list: T[]
  page: number
  size: number
}

/** 知识库 */
export interface KnowledgeBase {
  id: number
  owner_id?: number | null
  name: string
  description?: string
  visibility: 'public' | 'private'
  created_at?: string
  owner_name?: string
  doc_count?: number
}

/** 知识库文档 */
export interface DocumentItem {
  id: number
  kb_id: number
  filename: string
  file_path: string
  file_type: string
  visibility: string
  chunk_count: number
  status: string
  error?: string
  created_at?: string
}

/** 会话 */
export interface Conversation {
  id: string
  user_id: number
  kb_id?: number | null
  title: string
  created_at?: string
  updated_at?: string
  kb_name?: string
  messages?: Message[]
}

/** 引用来源 */
export interface Citation {
  doc_id: number
  chunk_index: number
  source_text: string
  title: string
  similarity: number
}

/** 聊天消息 */
export interface Message {
  id?: number
  conversation_id?: string
  role: 'user' | 'assistant'
  content: string
  created_at?: string
  conv_title?: string
  // 前端本地扩展字段
  citations?: Citation[]
  streaming?: boolean
  error?: boolean
  // Agent 模式：ReAct 推理轨迹（思考 / 工具调用 / 观察）
  agentSteps?: AgentStep[]
  agentMode?: boolean
}

/** Agent 推理步骤（与后端 orchestrator 事件对应） */
export interface AgentStep {
  type: 'thought' | 'tool_call' | 'observation' | 'message' | 'done' | 'error' | 'meta'
  content?: string
  name?: string
  args?: Record<string, unknown>
  // meta 事件：标识本次回答由哪个智能体（角色）产出
  role?: string
  role_label?: string
  // 前端本地扩展：步骤到达时间戳（用于时间线耗时展示）
  ts?: number
}

/** 住院记录 */
export interface Hospitalization {
  id: number
  patient_id: number
  admit_date: string
  discharge_date?: string | null
  department: string
  ward?: string
  bed_no?: string
  diagnosis?: string
  doctor_id?: number
  status: string
  total_cost: number
  created_at?: string
  patient_name?: string
  doctor_name?: string
}

/** 消费明细 */
export interface Bill {
  id: number
  patient_id: number
  bill_no: string
  category: string
  description?: string
  amount: number
  status: string
  created_at?: string
  patient_name?: string
}

/** 预约挂号 */
export interface Appointment {
  id: number
  patient_id: number
  doctor_id?: number
  department: string
  date: string
  time_slot: string
  symptom?: string
  fee: number
  status: string
  created_at?: string
  patient_name?: string
  doctor_name?: string
}

/** 护理记录 */
export interface NursingRecord {
  id: number
  patient_id: number
  nurse_id: number
  record_type: string
  content: string
  recorded_at?: string
  patient_name?: string
  nurse_name?: string
}

/** 排班 */
export interface Schedule {
  id: number
  staff_id: number
  work_date: string
  shift: string
  department?: string
  remark?: string
  status: string
  created_at?: string
  staff_name?: string
  staff_role?: string
}

/* ===== 仪表盘 ===== */
export interface UserStats {
  total: number
  by_role: Record<string, number>
}

export interface KbStats {
  kb_count: number
  doc_count: number
  doc_ready: number
  total_chunks: number
}

export interface BusinessStats {
  hospitalizations: number
  bills: number
  appointments: number
  nursing_records: number
  schedules: number
}

export interface ChatStats {
  conversations: number
  messages: number
  citations: number
}

export interface RevenueStats {
  paid: number
  unpaid: number
  total: number
}

export interface SystemOverview {
  users?: UserStats
  knowledge_bases?: KbStats
  business?: BusinessStats
  chat?: ChatStats
  revenue?: RevenueStats
  // 患者个人总览
  hospitalization_count?: number
  bill_count?: number
  appointment_count?: number
  conversation_count?: number
  total_paid?: number
  total_unpaid?: number
}

export interface DeptDistItem {
  department: string
  count: number
}

export interface BillCategoryItem {
  category: string
  count: number
  total: number
}
