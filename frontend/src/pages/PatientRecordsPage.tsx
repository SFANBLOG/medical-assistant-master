import { useEffect, useState } from 'react'
import { Card, Table, Tabs, Tag, Typography, App } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { patientApi } from '../api/endpoints'
import type { Bill, Hospitalization, Appointment } from '../types'

const HOSP_STATUS: Record<string, { text: string; color: string }> = {
  in_hospital: { text: '在院', color: 'processing' },
  discharged: { text: '已出院', color: 'default' },
}

const BILL_STATUS: Record<string, { text: string; color: string }> = {
  paid: { text: '已结算', color: 'success' },
  unpaid: { text: '未结算', color: 'warning' },
}

const APPT_STATUS: Record<string, { text: string; color: string }> = {
  booked: { text: '已预约', color: 'blue' },
  confirmed: { text: '已确认', color: 'processing' },
  visited: { text: '已就诊', color: 'success' },
  cancelled: { text: '已取消', color: 'default' },
}

export default function PatientRecordsPage() {
  const [hosp, setHosp] = useState<Hospitalization[]>([])
  const [bills, setBills] = useState<Bill[]>([])
  const [appts, setAppts] = useState<Appointment[]>([])
  const [loading, setLoading] = useState(true)
  const { message: toast } = App.useApp()

  useEffect(() => {
    Promise.all([patientApi.hospitalizations(), patientApi.bills(), patientApi.appointments()])
      .then(([h, b, a]) => {
        setHosp(h)
        setBills(b)
        setAppts(a)
      })
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }, [toast])

  const hospCols: ColumnsType<Hospitalization> = [
    { title: '入院日期', dataIndex: 'admit_date', width: 120 },
    { title: '出院日期', dataIndex: 'discharge_date', width: 120, render: (v?: string | null) => v || '-' },
    { title: '科室', dataIndex: 'department', width: 110 },
    { title: '病床', width: 110, render: (_, r) => `${r.ward || '-'} ${r.bed_no || ''}`.trim() },
    { title: '诊断', dataIndex: 'diagnosis', ellipsis: true },
    { title: '主治医生', dataIndex: 'doctor_name', width: 100, render: (v?: string) => v || '-' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: string) => (
        <Tag color={HOSP_STATUS[v]?.color}>{HOSP_STATUS[v]?.text ?? v}</Tag>
      ),
    },
    {
      title: '住院费用(元)',
      dataIndex: 'total_cost',
      width: 120,
      align: 'right',
      render: (v: number) => v.toLocaleString('zh-CN', { minimumFractionDigits: 2 }),
    },
  ]

  const billCols: ColumnsType<Bill> = [
    { title: '账单号', dataIndex: 'bill_no', width: 170 },
    { title: '类别', dataIndex: 'category', width: 90 },
    { title: '说明', dataIndex: 'description', ellipsis: true },
    {
      title: '金额(元)',
      dataIndex: 'amount',
      width: 120,
      align: 'right',
      render: (v: number) => v.toLocaleString('zh-CN', { minimumFractionDigits: 2 }),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: string) => <Tag color={BILL_STATUS[v]?.color}>{BILL_STATUS[v]?.text ?? v}</Tag>,
    },
    { title: '日期', dataIndex: 'created_at', width: 120 },
  ]

  const apptCols: ColumnsType<Appointment> = [
    { title: '科室', dataIndex: 'department', width: 110 },
    { title: '日期', dataIndex: 'date', width: 120 },
    { title: '时段', dataIndex: 'time_slot', width: 110 },
    { title: '医生', dataIndex: 'doctor_name', width: 100, render: (v?: string) => v || '-' },
    { title: '主诉', dataIndex: 'symptom', ellipsis: true, render: (v?: string) => v || '-' },
    { title: '挂号费(元)', dataIndex: 'fee', width: 110, align: 'right' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: string) => <Tag color={APPT_STATUS[v]?.color}>{APPT_STATUS[v]?.text ?? v}</Tag>,
    },
  ]

  const items = [
    {
      key: 'hosp',
      label: '住院信息',
      children: <Table rowKey="id" columns={hospCols} dataSource={hosp} loading={loading} size="small" pagination={{ pageSize: 8 }} />,
    },
    {
      key: 'bills',
      label: '消费明细',
      children: <Table rowKey="id" columns={billCols} dataSource={bills} loading={loading} size="small" pagination={{ pageSize: 10 }} />,
    },
    {
      key: 'appts',
      label: '预约挂号',
      children: <Table rowKey="id" columns={apptCols} dataSource={appts} loading={loading} size="small" pagination={false} />,
    },
  ]

  return (
    <Card title="我的健康档案">
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        患者可查询本人的最近住院信息、消费明细与预约挂号记录。
      </Typography.Paragraph>
      <Tabs items={items} />
    </Card>
  )
}
