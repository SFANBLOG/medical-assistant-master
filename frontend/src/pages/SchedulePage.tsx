import { useEffect, useState } from 'react'
import { Button, Card, DatePicker, Form, Input, Modal, Select, Table, Tag, App } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { scheduleApi } from '../api/endpoints'
import { ROLE_LABELS, SHIFT_LABELS } from '../types'
import type { Role, Schedule } from '../types'

const SHIFT_COLORS: Record<string, string> = { day: 'blue', night: 'purple', evening: 'orange', off: 'default' }
const DEPARTMENTS = ['心血管内科', '呼吸内科', '消化内科', '神经内科', '内分泌科', '儿科', '急诊科', '骨科']

interface FormValues {
  staff_id: number
  work_date: string
  shift: string
  department?: string
  remark?: string
}

export default function SchedulePage() {
  const [items, setItems] = useState<Schedule[]>([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm<FormValues>()
  const { message: toast } = App.useApp()

  const load = () => {
    setLoading(true)
    scheduleApi
      .list()
      .then(setItems)
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [toast])

  const submit = async (values: FormValues) => {
    try {
      await scheduleApi.create({
        staff_id: values.staff_id,
        work_date: dayjs(values.work_date).format('YYYY-MM-DD'),
        shift: values.shift,
        department: values.department,
        remark: values.remark,
      })
      toast.success('排班已保存')
      setModalOpen(false)
      load()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const columns: ColumnsType<Schedule> = [
    { title: '值班人员', dataIndex: 'staff_name', width: 130 },
    {
      title: '身份',
      dataIndex: 'staff_role',
      width: 80,
      render: (v: Role) => <Tag>{ROLE_LABELS[v] ?? v}</Tag>,
    },
    { title: '日期', dataIndex: 'work_date', width: 120 },
    {
      title: '班次',
      dataIndex: 'shift',
      width: 80,
      render: (v: string) => <Tag color={SHIFT_COLORS[v]}>{SHIFT_LABELS[v as keyof typeof SHIFT_LABELS] ?? v}</Tag>,
    },
    { title: '科室', dataIndex: 'department', width: 120, render: (v?: string) => v || '-' },
    { title: '备注', dataIndex: 'remark', ellipsis: true, render: (v?: string) => v || '-' },
  ]

  return (
    <Card
      title="排班管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新增排班
        </Button>
      }
    >
      <Table rowKey="id" columns={columns} dataSource={items} loading={loading} size="small" pagination={{ pageSize: 10 }} />

      <Modal title="新增排班" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()} okText="保存">
        <Form form={form} layout="vertical" onFinish={submit}>
          <Form.Item name="staff_id" label="值班人员" rules={[{ required: true, message: '请选择人员' }]}>
            <Select
              showSearch
              optionFilterProp="label"
              placeholder="选择医生/护士"
              options={items
                .map((s) => ({ value: s.staff_id, label: `${s.staff_name}（${ROLE_LABELS[s.staff_role ?? 'doctor']}）` }))
                .filter((v, i, arr) => arr.findIndex((x) => x.value === v.value) === i)}
            />
          </Form.Item>
          <Form.Item name="work_date" label="值班日期" rules={[{ required: true, message: '请选择日期' }]}>
            <DatePicker style={{ width: '100%' }} placeholder="选择日期" />
          </Form.Item>
          <Form.Item name="shift" label="班次" initialValue="day" rules={[{ required: true }]}>
            <Select
              options={Object.entries(SHIFT_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Form.Item name="department" label="科室">
            <Select allowClear placeholder="选填" options={DEPARTMENTS.map((d) => ({ value: d, label: d }))} />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input placeholder="选填" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
