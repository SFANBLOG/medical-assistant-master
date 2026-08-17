import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Drawer,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Upload,
  App,
  Typography,
} from 'antd'
import {
  DeleteOutlined,
  FileTextOutlined,
  InboxOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { UploadFile } from 'antd'
import { kbApi } from '../api/endpoints'
import { useAuth } from '../stores/auth'
import type { DocumentItem, KnowledgeBase } from '../types'

const STATUS_LABEL: Record<DocumentItem['status'], { text: string; color: string }> = {
  processing: { text: '处理中', color: 'processing' },
  ready: { text: '已完成', color: 'success' },
  failed: { text: '失败', color: 'error' },
}

export default function KbManagePage() {
  const user = useAuth((s) => s.user)
  const isDoctor = user?.role === 'doctor'
  const [kbs, setKbs] = useState<KnowledgeBase[]>([])
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm] = Form.useForm()
  const [drawerKb, setDrawerKb] = useState<KnowledgeBase | null>(null)
  const [docs, setDocs] = useState<DocumentItem[]>([])
  const [docsLoading, setDocsLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const { message: toast } = App.useApp()

  const load = () => {
    setLoading(true)
    kbApi
      .list()
      .then((items) => setKbs(items))
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setLoading(false))
  }
  useEffect(load, [toast])

  const loadDocs = (kbId: number) => {
    setDocsLoading(true)
    kbApi
      .documents(kbId)
      .then(setDocs)
      .catch((e) => toast.error((e as Error).message))
      .finally(() => setDocsLoading(false))
  }

  const createKb = async (values: { name: string; description?: string; visibility?: string }) => {
    try {
      await kbApi.create({
        name: values.name,
        description: values.description ?? '',
        visibility: values.visibility ?? 'private',
      })
      toast.success('创建成功')
      setCreateOpen(false)
      createForm.resetFields()
      load()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const removeKb = (kb: KnowledgeBase) => {
    Modal.confirm({
      title: `删除知识库「${kb.name}」？`,
      content: '将同时删除其全部文档与向量数据，该操作不可恢复。',
      okText: '删除',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await kbApi.remove(kb.id)
          toast.success('已删除')
          if (drawerKb?.id === kb.id) setDrawerKb(null)
          load()
        } catch (e) {
          toast.error((e as Error).message)
        }
      },
    })
  }

  const removeDoc = (kbId: number, doc: DocumentItem) => {
    Modal.confirm({
      title: `删除文档「${doc.filename}」？`,
      onOk: async () => {
        try {
          await kbApi.deleteDoc(kbId, doc.id)
          toast.success('已删除')
          loadDocs(kbId)
          load()
        } catch (e) {
          toast.error((e as Error).message)
        }
      },
    })
  }

  const handleUpload = async (kbId: number, file: File) => {
    setUploading(true)
    try {
      const doc = await kbApi.uploadDoc(kbId, file)
      toast.success(`「${doc.filename}」处理完成，共 ${doc.chunk_count} 个向量切片`)
      loadDocs(kbId)
      load()
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setUploading(false)
    }
    return false
  }

  const columns: ColumnsType<KnowledgeBase> = [
    { title: '名称', dataIndex: 'name', render: (v: string) => <Typography.Text strong>{v}</Typography.Text> },
    {
      title: '可见性',
      dataIndex: 'visibility',
      width: 100,
      render: (v: string) => (v === 'public' ? <Tag color="green">公开</Tag> : <Tag>私有</Tag>),
    },
    { title: '文档数', dataIndex: 'doc_count', width: 90, align: 'center' },
    { title: '向量切片', dataIndex: 'chunk_count', width: 100, align: 'center' },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 170,
      render: (v: string) => v.replace('T', ' ').slice(0, 19),
    },
    {
      title: '操作',
      width: 220,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<FileTextOutlined />} onClick={() => { setDrawerKb(record); loadDocs(record.id) }}>
            管理文档
          </Button>
          <Button size="small" danger type="text" icon={<DeleteOutlined />} onClick={() => removeKb(record)} />
        </Space>
      ),
    },
  ]

  const docColumns: ColumnsType<DocumentItem> = [
    { title: '文件名', dataIndex: 'filename', ellipsis: true },
    { title: '类型', dataIndex: 'file_type', width: 80 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (v: DocumentItem['status'], r) => (
        <Tag color={STATUS_LABEL[v].color}>
          {r.error ? `${STATUS_LABEL[v].text}：${r.error}` : STATUS_LABEL[v].text}
        </Tag>
      ),
    },
    { title: '切片数', dataIndex: 'chunk_count', width: 90, align: 'center' },
    { title: '上传时间', dataIndex: 'created_at', width: 170, render: (v: string) => v.replace('T', ' ').slice(0, 19) },
    {
      title: '操作',
      width: 80,
      render: (_, r) => (
        <Button size="small" danger type="text" icon={<DeleteOutlined />} onClick={() => removeDoc(drawerKb!.id, r)} />
      ),
    },
  ]

  return (
    <Card
      title="知识库管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建知识库
        </Button>
      }
    >
      <Table rowKey="id" columns={columns} dataSource={kbs} loading={loading} pagination={false} />

      <Modal
        title="新建知识库"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => createForm.submit()}
        okText="创建"
      >
        <Form form={createForm} layout="vertical" onFinish={createKb}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="如：我的健康资料" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="选填" />
          </Form.Item>
          <Form.Item name="visibility" label="可见性" initialValue="private" extra={isDoctor ? '医生可将知识库设为公开，供所有用户咨询' : '患者身份仅可创建私有知识库'}>
            <Select
              disabled={!isDoctor}
              options={[
                { value: 'private', label: '私有（仅自己可见）' },
                { value: 'public', label: '公开（所有人可见）' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title={drawerKb ? `管理文档 - ${drawerKb.name}` : '管理文档'}
        width={640}
        open={!!drawerKb}
        onClose={() => setDrawerKb(null)}
      >
        <Upload.Dragger
          multiple
          accept=".txt,.md,.pdf,.docx,.pptx"
          beforeUpload={(_file: UploadFile, files: UploadFile[]) => {
            const list = files as unknown as File[]
            void Promise.all(list.map((f) => handleUpload(drawerKb!.id, f)))
            return false
          }}
          disabled={uploading}
          showUploadList={false}
          style={{ marginBottom: 16 }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
          <p className="ant-upload-hint">支持 .txt / .md / .pdf / .docx / .pptx，单文件不超过 20MB</p>
        </Upload.Dragger>
        <Table
          rowKey="id"
          columns={docColumns}
          dataSource={docs}
          loading={docsLoading}
          pagination={false}
          size="small"
        />
      </Drawer>
    </Card>
  )
}
