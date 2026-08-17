import { useEffect, useState } from 'react'
import { Button, Card, Form, Input, Modal, Select, Table, Tabs, Tag, App } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined } from '@ant-design/icons'
import { nurseApi, scheduleApi } from '../api/endpoints'
import { useAuth } from '../stores/auth'
import { SHIFT_LABELS } from '../types'
import type { NursingRecord, PatientSummary, Schedule } from '../types'

const RECORD_TYPE_LABELS: Record<string, string> = {
  daily: '日常护理',
  medication: '给药护理',
  vitals: '生命体征',
  other: '其他',
}

export default function NurseWorkbenchPage() {
  const user = useAuth((s) => s.user)
  const [patients, setPatients] = useState<PatientSummary[]>([])
  const [records, setRecords] = useState<NursingRecord[]>([])
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm<{ patient_id: number; record_type: string; content: string }>()
  const { message: toast } = App.useApp()

  const load = () => {
    setLoading(true)
    Promise.all([
      nurseApi.patients(),
      nurseApi.nursingRecords(),
      scheduleApi.list({ staff_id: user?.id }),
    ])
      .then(([p, r, s]) => {
        setPatients(p)
        setRecords(r)
        setSchedules(s)
      })
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [toast, user?.id])

  const submit = async (values: { patient_id: number; record_type: string; content: string }) => {
    try {
      await nurseApi.createNursingRecord({
        patient_id: values.patient_id,
        content: values.content,
        record_type: values.record_type,
      })
      toast.success('护理记录已保存')
      setModalOpen(false)
      load()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const patientCols: ColumnsType<PatientSummary> = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '姓名', dataIndex: 'display_name', width: 120, render: (v?: string) => v || '-' },
    { title: '用户名', dataIndex: 'username', width: 130 },
    { title: '当前状态', dataIndex: 'current_status', width: 90, render: (v?: string) => (v ? <Tag color="processing">在院</Tag> : <Tag>非住院</Tag>) },
    { title: '科室', dataIndex: 'current_department', width: 110, render: (v?: string) => v || '-' },
    { title: '床位', dataIndex: 'current_bed', width: 80, render: (v?: string) => v || '-' },
  ]

  const recordCols: ColumnsType<NursingRecord> = [
    { title: '患者', dataIndex: 'patient_name', width: 110 },
    { title: '类型', dataIndex: 'record_type', width: 90, render: (v: string) => <Tag>{RECORD_TYPE_LABELS[v] ?? v}</Tag> },
    { title: '记录内容', dataIndex: 'content', ellipsis: true },
    { title: '记录护士', dataIndex: 'nurse_name', width: 110, render: (v?: string) => v || '-' },
    { title: '时间', dataIndex: 'recorded_at', width: 130 },
  ]

  const schedCols: ColumnsType<Schedule> = [
    { title: '日期', dataIndex: 'work_date', width: 120 },
    { title: '班次', dataIndex: 'shift', width: 80, render: (v: string) => <Tag>{SHIFT_LABELS[v as keyof typeof SHIFT_LABELS] ?? v}</Tag> },
    { title: '科室', dataIndex: 'department', width: 120, render: (v?: string) => v || '-' },
    { title: '备注', dataIndex: 'remark', render: (v?: string) => v || '-' },
  ]

  const items = [
    {
      key: 'patients',
      label: `患者信息 (${patients.length})`,
      children: <Table rowKey="id" columns={patientCols} dataSource={patients} loading={loading} size="small" pagination={{ pageSize: 10 }} />,
    },
    {
      key: 'records',
      label: `护理记录 (${records.length})`,
      children: (
        <div>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            style={{ marginBottom: 16 }}
            onClick={() => {
              form.resetFields()
              setModalOpen(true)
            }}
          >
            新增护理记录
          </Button>
          <Table rowKey="id" columns={recordCols} dataSource={records} loading={loading} size="small" pagination={{ pageSize: 10 }} />
        </div>
      ),
    },
    {
      key: 'schedule',
      label: `我的排班 (${schedules.length})`,
      children: <Table rowKey="id" columns={schedCols} dataSource={schedules} loading={loading} size="small" pagination={false} />,
    },
  ]

  return (
    <Card title="护理工作台">
      <Tabs items={items} />
      <Modal title="新增护理记录" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()} okText="保存">
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
          <Form.Item name="record_type" label="记录类型" initialValue="daily">
            <Select options={Object.entries(RECORD_TYPE_LABELS).map(([value, label]) => ({ value, label }))} />
          </Form.Item>
          <Form.Item name="content" label="记录内容" rules={[{ required: true, message: '请输入内容' }]}>
            <Input.TextArea rows={3} placeholder="如：生命体征平稳，遵医嘱给药并观察反应" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
