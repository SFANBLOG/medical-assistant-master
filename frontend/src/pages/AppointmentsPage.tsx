import { useEffect, useState } from 'react'
import { Button, Card, DatePicker, Form, Input, Select, Table, Tag, App, Row, Col } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { patientApi } from '../api/endpoints'
import type { Appointment } from '../types'

const DEPARTMENTS = [
  '心血管内科', '呼吸内科', '消化内科', '神经内科', '内分泌科',
  '肾内科', '风湿免疫科', '感染科', '骨科', '皮肤科', '儿科', '妇产科', '普外科',
]
const SLOTS = ['08:00-08:30', '08:30-09:00', '09:00-09:30', '14:00-14:30', '14:30-15:00']

const APPT_STATUS: Record<string, { text: string; color: string }> = {
  booked: { text: '已预约', color: 'blue' },
  confirmed: { text: '已确认', color: 'processing' },
  visited: { text: '已就诊', color: 'success' },
  cancelled: { text: '已取消', color: 'default' },
}

interface DoctorOption {
  id: number
  username: string
  display_name: string
}

interface FormValues {
  department: string
  date: string
  time_slot: string
  doctor_id?: number
  symptom?: string
}

export default function AppointmentsPage() {
  const [items, setItems] = useState<Appointment[]>([])
  const [doctors, setDoctors] = useState<DoctorOption[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm<FormValues>()
  const { message: toast } = App.useApp()

  const load = () => {
    setLoading(true)
    Promise.all([patientApi.appointments(), patientApi.doctors()])
      .then(([a, d]) => {
        setItems(a)
        setDoctors(d)
      })
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [toast])

  const submit = async (values: FormValues) => {
    setSubmitting(true)
    try {
      await patientApi.createAppointment({
        department: values.department,
        date: dayjs(values.date).format('YYYY-MM-DD'),
        time_slot: values.time_slot,
        doctor_id: values.doctor_id,
        symptom: values.symptom,
      })
      toast.success('预约成功')
      form.resetFields()
      load()
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const cancel = async (id: number) => {
    try {
      await patientApi.cancelAppointment(id)
      toast.success('已取消预约')
      load()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const columns: ColumnsType<Appointment> = [
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
    {
      title: '操作',
      width: 90,
      render: (_, r) =>
        r.status !== 'cancelled' && r.status !== 'visited' ? (
          <Button size="small" danger type="link" onClick={() => cancel(r.id)}>
            取消
          </Button>
        ) : (
          '-'
        ),
    },
  ]

  return (
    <Card title="预约挂号">
      <Card size="small" title="在线挂号" style={{ marginBottom: 16 }}>
        <Form form={form} layout="vertical" onFinish={submit}>
          <Row gutter={16}>
            <Col xs={24} md={8}>
              <Form.Item name="department" label="就诊科室" rules={[{ required: true, message: '请选择科室' }]}>
                <Select placeholder="选择科室" options={DEPARTMENTS.map((d) => ({ value: d, label: d }))} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="doctor_id" label="选择医生（选填）">
                <Select
                  allowClear
                  placeholder="不选由科室随机排号"
                  options={doctors.map((d) => ({ value: d.id, label: d.display_name || d.username }))}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="date" label="就诊日期" rules={[{ required: true, message: '请选择日期' }]}>
                <DatePicker style={{ width: '100%' }} placeholder="选择日期" disabledDate={(d) => d.isBefore(dayjs(), 'day')} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="time_slot" label="就诊时段" rules={[{ required: true, message: '请选择时段' }]}>
                <Select placeholder="选择时段" options={SLOTS.map((s) => ({ value: s, label: s }))} />
              </Form.Item>
            </Col>
            <Col xs={24} md={16}>
              <Form.Item name="symptom" label="主诉/症状（选填）">
                <Input placeholder="简单描述症状，便于医生提前了解" />
              </Form.Item>
            </Col>
          </Row>
          <Button type="primary" htmlType="submit" loading={submitting}>
            提交预约
          </Button>
        </Form>
      </Card>
      <Table rowKey="id" columns={columns} dataSource={items} loading={loading} size="small" pagination={false} />
    </Card>
  )
}
