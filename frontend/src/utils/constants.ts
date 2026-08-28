/** 通用常量：枚举值 → 中文标签 与 颜色 */

export const HOSPITAL_STATUS: Record<string, { label: string; type: string }> = {
  in_hospital: { label: '住院中', type: 'primary' },
  discharged: { label: '已出院', type: 'success' },
  transferred: { label: '已转院', type: 'warning' },
}

export const BILL_STATUS: Record<string, { label: string; type: string }> = {
  paid: { label: '已支付', type: 'success' },
  unpaid: { label: '未支付', type: 'warning' },
}

export const APPOINTMENT_STATUS: Record<string, { label: string; type: string }> = {
  booked: { label: '已预约', type: 'primary' },
  confirmed: { label: '已确认', type: 'success' },
  visited: { label: '已就诊', type: 'info' },
  cancelled: { label: '已取消', type: 'danger' },
}

export const NURSING_TYPES: Record<string, { label: string; type: string }> = {
  daily: { label: '日常护理', type: 'primary' },
  medication: { label: '用药护理', type: 'success' },
  vitals: { label: '生命体征', type: 'warning' },
  other: { label: '其他', type: 'info' },
}

export const SCHEDULE_SHIFTS: Record<string, { label: string; type: string }> = {
  day: { label: '早班', type: 'primary' },
  evening: { label: '中班', type: 'warning' },
  night: { label: '夜班', type: 'info' },
  off: { label: '休息', type: 'danger' },
}

export const SCHEDULE_STATUS: Record<string, { label: string; type: string }> = {
  on_duty: { label: '在岗', type: 'success' },
  off: { label: '休班', type: 'info' },
}

export const DEPARTMENTS = [
  '内科', '外科', '心内科', '呼吸科', '消化科', '神经科',
  '内分泌科', '肾内科', '风湿免疫科', '感染科',
  '急诊科', '骨科', '皮肤科', '妇产科', '儿科', '中医科',
]

export const TIME_SLOTS = [
  '08:00-09:00', '09:00-10:00', '10:00-11:00',
  '14:00-15:00', '15:00-16:00',
]

export const BILL_CATEGORIES = ['挂号', '检查', '检验', '药品', '住院', '门诊']

export function pickStatus(map: Record<string, { label: string; type: string }>, value?: string) {
  return map[value || ''] || { label: value || '-', type: 'info' }
}
