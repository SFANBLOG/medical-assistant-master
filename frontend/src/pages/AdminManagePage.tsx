import { useEffect, useState } from 'react'
import {
  Button, Card, Col, Form, Input, Modal, Row, Select, Space, Statistic, Table, Tag, Tabs, App,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { DeleteOutlined, PlusOutlined, UserOutlined } from '@ant-design/icons'
import { adminApi } from '../api/endpoints'
import { ROLE_COLORS, ROLE_LABELS } from '../types'
import type { AdminUserRow, Role } from '../types'

const ROLE_OPTIONS = (Object.keys(ROLE_LABELS) as Role[]).map((value) => ({ value, label: ROLE_LABELS[value] }))

interface AdminStats {
  user_count: number
  kb_count: number
  doc_count: number
  chunk_count: number
  conversation_count: number
  message_count: number
  hospitalization_count: number
  bill_total: number
}

export default function AdminManagePage() {
  return (
    <Card title="系统管理">
      <Tabs
        items={[
          { key: 'users', label: '用户管理', children: <UsersTab /> },
          { key: 'stats', label: '系统看板', children: <StatsTab /> },
        ]}
      />
    </Card>
  )
}

function UsersTab() {
  const [items, setItems] = useState<AdminUserRow[]>([])
  const [total, setTotal] = useState(0)
  const [roleFilter, setRoleFilter] = useState('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [editRow, setEditRow] = useState<AdminUserRow | null>(null)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const { message: toast, modal } = App.useApp()

  const load = () => {
    setLoading(true)
    adminApi
      .users({ role: roleFilter || undefined, q, page, page_size: 10 })
      .then((d) => {
        setItems(d.items)
        setTotal(d.total)
      })
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [roleFilter, q, page, toast])

  const createUser = async (values: { username: string; password: string; role: Role; display_name?: string }) => {
    try {
      await adminApi.createUser(values)
      toast.success('用户已创建')
      setCreateOpen(false)
      createForm.resetFields()
      load()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const editUser = async (values: { role?: Role; display_name?: string; reset_password?: string }) => {
    if (!editRow) return
    try {
      await adminApi.updateUser(editRow.id, values)
      toast.success('用户已更新')
      setEditRow(null)
      load()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const removeUser = (r: AdminUserRow) => {
    modal.confirm({
      title: `删除用户「${r.username}」？`,
      content: '将同时级联删除其业务数据，该操作不可恢复。',
      okText: '删除',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await adminApi.removeUser(r.id)
          toast.success('已删除')
          load()
        } catch (e) {
          toast.error((e as Error).message)
        }
      },
    })
  }

  const columns: ColumnsType<AdminUserRow> = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '用户名', dataIndex: 'username', width: 150 },
    { title: '姓名', dataIndex: 'display_name', width: 130 },
    {
      title: '身份',
      dataIndex: 'role',
      width: 90,
      render: (v: Role) => <Tag color={ROLE_COLORS[v]}>{ROLE_LABELS[v]}</Tag>,
    },
    { title: '注册时间', dataIndex: 'created_at', render: (v: string) => v.replace('T', ' ').slice(0, 19) },
    {
      title: '操作',
      width: 160,
      render: (_, r) => (
        <Space>
          <Button
            size="small"
            type="link"
            onClick={() => {
              setEditRow(r)
              editForm.setFieldsValue({ role: r.role, display_name: r.display_name })
            }}
          >
            编辑
          </Button>
          <Button size="small" danger type="text" icon={<DeleteOutlined />} onClick={() => removeUser(r)} />
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索用户名/姓名"
          allowClear
          style={{ width: 220 }}
          onSearch={(v) => {
            setPage(1)
            setQ(v)
          }}
        />
        <Select
          allowClear
          placeholder="按身份筛选"
          style={{ width: 140 }}
          value={roleFilter || undefined}
          onChange={(v) => {
            setPage(1)
            setRoleFilter(v ?? '')
          }}
          options={ROLE_OPTIONS}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建用户
        </Button>
      </Space>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={{ current: page, pageSize: 10, total, onChange: setPage, showSizeChanger: false }}
      />

      <Modal title="新建用户" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => createForm.submit()} okText="创建">
        <Form form={createForm} layout="vertical" onFinish={createUser}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input placeholder="3-32 个字符" />
          </Form.Item>
          <Form.Item name="display_name" label="姓名/昵称">
            <Input placeholder="选填" />
          </Form.Item>
          <Form.Item name="role" label="身份" rules={[{ required: true, message: '请选择身份' }]}>
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 6, message: '密码至少 6 位' }]}>
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="编辑用户" open={!!editRow} onCancel={() => setEditRow(null)} onOk={() => editForm.submit()} okText="保存">
        <Form form={editForm} layout="vertical" onFinish={editUser}>
          <Form.Item name="role" label="身份" rules={[{ required: true }]}>
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="display_name" label="姓名/昵称">
            <Input />
          </Form.Item>
          <Form.Item name="reset_password" label="重置密码（留空则不修改）">
            <Input.Password placeholder="至少 6 位" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

function StatsTab() {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const { message: toast } = App.useApp()

  useEffect(() => {
    adminApi
      .stats()
      .then(setStats)
      .catch((e) => toast.error((e as Error).message))
  }, [toast])

  return (
    <Row gutter={[16, 16]}>
      <Col xs={12} md={8} lg={4}><Card><Statistic title="用户总数" value={stats?.user_count ?? 0} prefix={<UserOutlined />} /></Card></Col>
      <Col xs={12} md={8} lg={4}><Card><Statistic title="知识库" value={stats?.kb_count ?? 0} /></Card></Col>
      <Col xs={12} md={8} lg={4}><Card><Statistic title="文档" value={stats?.doc_count ?? 0} /></Card></Col>
      <Col xs={12} md={8} lg={4}><Card><Statistic title="向量切片" value={stats?.chunk_count ?? 0} /></Card></Col>
      <Col xs={12} md={8} lg={4}><Card><Statistic title="咨询会话" value={stats?.conversation_count ?? 0} /></Card></Col>
      <Col xs={12} md={8} lg={4}><Card><Statistic title="消息总数" value={stats?.message_count ?? 0} /></Card></Col>
      <Col xs={12} md={8} lg={4}><Card><Statistic title="住院记录" value={stats?.hospitalization_count ?? 0} /></Card></Col>
      <Col xs={12} md={8} lg={4}><Card><Statistic title="消费总额(元)" value={stats?.bill_total ?? 0} /></Card></Col>
    </Row>
  )
}
