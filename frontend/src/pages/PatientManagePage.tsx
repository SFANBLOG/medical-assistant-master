import { useEffect, useState } from 'react'
import { Card, Input, Space, Table, Tag, App } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { SearchOutlined } from '@ant-design/icons'
import { doctorApi } from '../api/endpoints'
import type { Hospitalization, PatientSummary } from '../types'

export default function PatientManagePage() {
  const [items, setItems] = useState<PatientSummary[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const { message: toast } = App.useApp()

  const load = () => {
    setLoading(true)
    doctorApi
      .patients({ q, page, page_size: 10 })
      .then((data) => {
        setItems(data.items)
        setTotal(data.total)
      })
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [q, page, toast])

  const columns: ColumnsType<PatientSummary> = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '用户名', dataIndex: 'username', width: 140 },
    { title: '姓名', dataIndex: 'display_name', width: 120 },
    {
      title: '当前住院状态',
      width: 200,
      render: (_, r) =>
        r.latest_admission ? (
          <Tag color={r.latest_admission.status === 'in_hospital' ? 'processing' : 'default'}>
            {r.latest_admission.status === 'in_hospital' ? '在院' : '已出院'} · {r.latest_admission.department}
          </Tag>
        ) : (
          <Tag>无住院记录</Tag>
        ),
    },
    { title: '注册时间', dataIndex: 'created_at', render: (v?: string) => (v ? v.replace('T', ' ').slice(0, 16) : '-') },
  ]

  return (
    <Card title="患者管理">
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索患者姓名或用户名"
          allowClear
          style={{ width: 260 }}
          prefix={<SearchOutlined />}
          onSearch={(v) => {
            setPage(1)
            setQ(v)
          }}
        />
        <Tag>共 {total} 位患者</Tag>
      </Space>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={{ current: page, pageSize: 10, total, onChange: setPage, showSizeChanger: false }}
        expandable={{
          expandedRowRender: (record) => <PatientHospitals patientId={record.id} />,
        }}
      />
    </Card>
  )
}

function PatientHospitals({ patientId }: { patientId: number }) {
  const [rows, setRows] = useState<Hospitalization[]>([])
  const [loading, setLoading] = useState(true)
  const { message: toast } = App.useApp()

  useEffect(() => {
    doctorApi
      .patientHospitalizations(patientId)
      .then(setRows)
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }, [patientId, toast])

  return (
    <Table
      rowKey="id"
      size="small"
      columns={[
        { title: '入院日期', dataIndex: 'admit_date', width: 120 },
        { title: '出院日期', dataIndex: 'discharge_date', width: 120, render: (v?: string | null) => v || '-' },
        { title: '科室', dataIndex: 'department', width: 110 },
        { title: '诊断', dataIndex: 'diagnosis', ellipsis: true },
        { title: '主治医生', dataIndex: 'doctor_name', width: 110, render: (v?: string) => v || '-' },
        { title: '费用(元)', dataIndex: 'total_cost', width: 100, align: 'right' },
      ]}
      dataSource={rows}
      loading={loading}
      pagination={false}
    />
  )
}
