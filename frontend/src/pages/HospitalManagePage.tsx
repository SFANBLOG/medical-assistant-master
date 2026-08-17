import { useEffect, useState } from 'react'
import {
  Button, Card, DatePicker, Form, Input, Modal, Radio, Select, Space, Table, Tag, App, Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { doctorApi } from '../api/endpoints'
import type { Hospitalization, PatientSummary } from '../types'

const HOSP_STATUS: Record<string, { text: string; color: string }> = {
  in_hospital: { text: '在院', color: 'processing' },
  discharged: { text: '已出院', color: 'default' },
}

const DEPARTMENTS = [
  '心血管内科', '呼吸内科', '消化内科', '神经内科', '内分泌科',
  '肾内科', '风湿免疫科', '感染科', '骨科', '皮肤科', '儿科', '妇产科', '普外科',
]

interface FormValues {
  patient_id: number
  department: string
  admit_date: string
  diagnosis?: string
  ward?: string
  bed_no?: string
}

export default function HospitalManagePage() {
  const [items, setItems] = useState<Hospitalization[]>([])
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [patients, setPatients] = useState<PatientSummary[]>([])
  const [form] = Form.useForm<FormValues>()
  const { message: toast, modal } = App.useApp()

  const load = () => {
    setLoading(true)
    doctorApi
      .hospitalizations({ status: status || undefined })
      .then(setItems)
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [status, toast])

  useEffect(() => {
    doctorApi
      .patients({ page_size: 50 })
      .then((d) => setPatients(d.items))
      .catch(() => {})
  }, [])

  const openModal = () => {
    form.resetFields()
    setModalOpen(true)
  }

  const submit = async (values: FormValues) => {
    setSubmitting(true)
    try {
      await doctorApi.createHospitalization({
        patient_id: values.patient_id,
        department: values.department,
        admit_date: dayjs(values.admit_date).format('YYYY-MM-DD'),
        diagnosis: values.diagnosis,
        ward: values.ward,
        bed_no: values.bed_no,
      })
      toast.success('住院登记成功')
      setModalOpen(false)
      load()
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const discharge = (r: Hospitalization) => {
    modal.confirm({
      title: `办理出院（${r.diagnosis || r.department}）？`,
      okText: '确认出院',
      onOk: async () => {
        try {
          await doctorApi.updateHospitalization(r.id, { status: 'discharged', discharge_date: dayjs().format('YYYY-MM-DD') })
          toast.success('已办理出院')
          load()
        } catch (e) {
          toast.error((e as Error).message)
        }
      },
    })
  }

  const columns: ColumnsType<Hospitalization> = [
    { title: '患者', width: 110, render: (_, r) => r.patient_name || r.patient_username || `#${r.patient_id}` },
    { title: '入院日期', dataIndex: 'admit_date', width: 115 },
    { title: '出院日期', dataIndex: 'discharge_date', width: 115, render: (v?: string | null) => v || '-' },
    { title: '科室', dataIndex: 'department', width: 100 },
    { title: '病床', width: 90, render: (_, r) => `${r.ward || '-'} ${r.bed_no || ''}`.trim() },
    { title: '诊断', dataIndex: 'diagnosis', ellipsis: true, render: (v?: string) => v || '-' },
    { title: '主治医生', dataIndex: 'doctor_name', width: 100, render: (v?: string) => v || '-' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: string) => <Tag color={HOSP_STATUS[v]?.color}>{HOSP_STATUS[v]?.text ?? v}</Tag>,
    },
    {
      title: '费用(元)',
      dataIndex: 'total_cost',
      width: 110,
      align: 'right',
      render: (v: number) => v.toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      width: 100,
      render: (_, r) =>
        r.status === 'in_hospital' ? (
          <Button size="small" type="link" onClick={() => discharge(r)}>
            办理出院
          </Button>
        ) : (
          '-'
        ),
    },
  ]

  return (
    <Card
      title="住院信息管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={openModal}>
          新增住院
        </Button>
      }
    >
      <Space style={{ marginBottom: 16 }}>
        <Radio.Group value={status} onChange={(e) => setStatus(e.target.value)}>
          <Radio.Button value="">全部</Radio.Button>
          <Radio.Button value="in_hospital">在院</Radio.Button>
          <Radio.Button value="discharged">已出院</Radio.Button>
        </Radio.Group>
        <Typography.Text type="secondary">共 {items.length} 条记录</Typography.Text>
      </Space>
      <Table rowKey="id" columns={columns} dataSource={items} loading={loading} size="small" pagination={{ pageSize: 10 }} />

      <Modal
        title="新增住院登记"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        okText="登记"
        confirmLoading={submitting}
      >
        <Form form={form} layout="vertical" onFinish={submit}>
          <Form.Item name="patient_id" label="患者" rules={[{ required: true, message: '请选择患者' }]}>
            <Select
              showSearch
              optionFilterProp="label"
              placeholder="选择患者"
              options={patients.map((p) => ({
                value: p.id,
                label: `${p.display_name || p.username}（#${p.id}）`,
              }))}
            />
          </Form.Item>
          <Form.Item name="department" label="科室" rules={[{ required: true, message: '请选择科室' }]}>
            <Select placeholder="选择科室" options={DEPARTMENTS.map((d) => ({ value: d, label: d }))} />
          </Form.Item>
          <Form.Item name="admit_date" label="入院日期" rules={[{ required: true, message: '请选择日期' }]}>
            <DatePicker style={{ width: '100%' }} placeholder="选择日期" />
          </Form.Item>
          <Form.Item name="diagnosis" label="初步诊断">
            <Input placeholder="选填" />
          </Form.Item>
          <Space.Compact style={{ width: '100%' }}>
            <Form.Item name="ward" label="病区" style={{ marginBottom: 0, width: '50%' }}>
              <Input placeholder="病区" />
            </Form.Item>
            <Form.Item name="bed_no" label="床号" style={{ marginBottom: 0, width: '50%' }}>
              <Input placeholder="床号" />
            </Form.Item>
          </Space.Compact>
        </Form>
      </Modal>
    </Card>
  )
}
