import { useEffect, useState } from 'react'
import { Card, Col, Row, Statistic, Table, Tag, Typography, App, Spin } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { dashboardApi } from '../api/endpoints'
import { ROLE_COLORS, ROLE_LABELS } from '../types'
import type { DashboardStats, RecentConversation, Role } from '../types'

export default function DoctorWorkbenchPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [recent, setRecent] = useState<RecentConversation[]>([])
  const [loading, setLoading] = useState(true)
  const { message: toast } = App.useApp()

  useEffect(() => {
    Promise.all([dashboardApi.stats(), dashboardApi.recent()])
      .then(([s, r]) => {
        setStats(s)
        setRecent(r)
      })
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }, [toast])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />

  const columns: ColumnsType<RecentConversation> = [
    { title: '用户', dataIndex: 'username', width: 140 },
    {
      title: '身份',
      dataIndex: 'role',
      width: 90,
      render: (v: Role) => <Tag color={ROLE_COLORS[v]}>{ROLE_LABELS[v]}</Tag>,
    },
    { title: '咨询标题', dataIndex: 'title', ellipsis: true },
    { title: '知识库', dataIndex: 'kb_name', width: 160, render: (v?: string) => v || '-' },
    { title: '时间', dataIndex: 'created_at', width: 170, render: (v: string) => v.replace('T', ' ').slice(0, 19) },
  ]

  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        医生工作台
      </Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={12} md={8} lg={4}><Card><Statistic title="知识库（全系统）" value={stats?.kb_count ?? 0} /></Card></Col>
        <Col xs={12} md={8} lg={4}><Card><Statistic title="文档" value={stats?.doc_count ?? 0} /></Card></Col>
        <Col xs={12} md={8} lg={4}><Card><Statistic title="向量切片" value={stats?.chunk_count ?? 0} /></Card></Col>
        <Col xs={12} md={8} lg={6}><Card><Statistic title="全系统咨询会话" value={stats?.conversation_count ?? 0} /></Card></Col>
        <Col xs={12} md={8} lg={6}><Card><Statistic title="消息总数" value={stats?.message_count ?? 0} /></Card></Col>
      </Row>
      <Card title="最近咨询（全系统）" style={{ marginTop: 16 }}>
        <Table rowKey="id" columns={columns} dataSource={recent} pagination={false} size="small" />
      </Card>
    </div>
  )
}
