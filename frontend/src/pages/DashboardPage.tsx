import { useEffect, useState } from 'react'
import { Card, Col, Row, Statistic, Spin, Alert, Typography } from 'antd'
import {
  DatabaseOutlined,
  FileTextOutlined,
  PartitionOutlined,
  MessageOutlined,
  CommentOutlined,
} from '@ant-design/icons'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { dashboardApi } from '../api/endpoints'
import { ROLE_LABELS } from '../types'
import type { DashboardStats } from '../types'

const PIE_COLORS = ['#1677ff', '#fa541c', '#722ed1', '#52c41a', '#eb2f96']

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    dashboardApi
      .stats()
      .then(setStats)
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '120px auto' }} />
  if (error) return <Alert type="error" message="加载失败" description={error} showIcon />

  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        数据仪表盘
      </Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={12} md={8} lg={4}>
          <Card>
            <Statistic title="知识库" value={stats?.kb_count ?? 0} prefix={<DatabaseOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={8} lg={4}>
          <Card>
            <Statistic title="文档" value={stats?.doc_count ?? 0} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={8} lg={4}>
          <Card>
            <Statistic title="向量切片" value={stats?.chunk_count ?? 0} prefix={<PartitionOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={8} lg={6}>
          <Card>
            <Statistic title="咨询会话" value={stats?.conversation_count ?? 0} prefix={<MessageOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={8} lg={6}>
          <Card>
            <Statistic title="消息条数" value={stats?.message_count ?? 0} prefix={<CommentOutlined />} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="各知识库文档数">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={stats?.docs_by_kb ?? []}>
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="doc_count" name="文档数" fill="#1677ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        {stats?.role_breakdown && (
          <Col xs={24} lg={10}>
            <Card title="用户身份分布（全系统）">
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={stats.role_breakdown.map((r) => ({
                      name: ROLE_LABELS[r.role as keyof typeof ROLE_LABELS] ?? r.role,
                      value: r.count,
                    }))}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label
                  >
                    {stats.role_breakdown.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Legend />
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        )}
      </Row>
    </div>
  )
}
