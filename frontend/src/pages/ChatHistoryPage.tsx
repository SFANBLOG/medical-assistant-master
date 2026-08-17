import { useEffect, useState } from 'react'
import { Button, Card, Input, Space, Table, Tag, App, Typography } from 'antd'
import { DeleteOutlined, MessageOutlined, RightOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import { chatApi } from '../api/endpoints'
import type { Conversation } from '../types'

export default function ChatHistoryPage() {
  const [items, setItems] = useState<Conversation[]>([])
  const [total, setTotal] = useState(0)
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const { message: toast } = App.useApp()
  const navigate = useNavigate()

  const load = () => {
    setLoading(true)
    chatApi
      .conversations({ q, page, page_size: 10 })
      .then((data) => {
        setItems(data.items)
        setTotal(data.total)
      })
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [q, page, toast])

  const remove = async (id: string) => {
    try {
      await chatApi.remove(id)
      toast.success('已删除')
      load()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const columns: ColumnsType<Conversation> = [
    {
      title: '标题',
      dataIndex: 'title',
      ellipsis: true,
      render: (v: string) => (
        <Typography.Text strong>
          <MessageOutlined style={{ marginRight: 6 }} />
          {v}
        </Typography.Text>
      ),
    },
    { title: '知识库', dataIndex: 'kb_name', width: 180, render: (v?: string) => v || '-' },
    { title: '消息数', dataIndex: 'message_count', width: 90, align: 'center' },
    { title: '更新时间', dataIndex: 'updated_at', width: 170 },
    {
      title: '操作',
      width: 220,
      render: (_, record) => (
        <Space>
          <Button size="small" type="link" icon={<RightOutlined />} onClick={() => navigate(`/chat?conversation=${record.id}`)}>
            继续咨询
          </Button>
          <Button size="small" type="link" onClick={() => navigate(`/chat/history/${record.id}`)}>
            查看记录
          </Button>
          <Button size="small" danger type="text" icon={<DeleteOutlined />} onClick={() => remove(record.id)} />
        </Space>
      ),
    },
  ]

  return (
    <Card title="咨询历史">
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索会话标题"
          allowClear
          style={{ width: 260 }}
          onSearch={(v) => {
            setPage(1)
            setQ(v)
          }}
        />
        <Tag>{total} 条</Tag>
      </Space>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={{
          current: page,
          pageSize: 10,
          total,
          onChange: setPage,
          showSizeChanger: false,
        }}
      />
    </Card>
  )
}
