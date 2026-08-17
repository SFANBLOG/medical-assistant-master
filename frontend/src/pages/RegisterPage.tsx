import { Button, Card, Form, Input, Select, App, Typography } from 'antd'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../stores/auth'
import { ROLE_LABELS } from '../types'
import type { Role } from '../types'

interface FormValues {
  username: string
  password: string
  confirm: string
  role: Role
  display_name?: string
}

const ROLE_HINTS: Record<Role, string> = {
  patient: '可查询住院与消费信息、预约挂号并进行智能咨询',
  doctor: '可管理公开知识库、查看全系统数据、管理患者与住院信息',
  nurse: '可查看患者信息、记录护理记录并查看排班',
  public: '可浏览健康资讯、就诊指南并进行智能咨询与预约挂号',
  admin: '可管理系统用户、知识库与全系统数据看板',
}

export default function RegisterPage() {
  const register = useAuth((s) => s.register)
  const navigate = useNavigate()
  const { message } = App.useApp()

  const onFinish = async (values: FormValues) => {
    try {
      await register(values.username, values.password, values.role, values.display_name)
      message.success('注册成功')
      navigate('/')
    } catch (e) {
      message.error((e as Error).message)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #e8f4fd 0%, #f0fff4 100%)',
      }}
    >
      <Card style={{ width: 420, boxShadow: '0 8px 24px rgba(0,0,0,0.08)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Typography.Title level={3} style={{ marginTop: 0, marginBottom: 4 }}>
            注册账号
          </Typography.Title>
          <Typography.Text type="secondary">选择身份，开启医疗知识智能问答</Typography.Text>
        </div>
        <Form<FormValues> layout="vertical" onFinish={onFinish}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input placeholder="3-32 个字符" />
          </Form.Item>
          <Form.Item name="display_name" label="昵称">
            <Input placeholder="选填，默认为用户名" />
          </Form.Item>
          <Form.Item name="role" label="身份" rules={[{ required: true, message: '请选择身份' }]}>
            <Select
              placeholder="请选择身份"
              options={Object.entries(ROLE_LABELS).map(([value, label]) => ({
                value: value as Role,
                label,
              }))}
            />
          </Form.Item>
          <Form.Item shouldUpdate>
            {({ getFieldValue }) => {
              const role = getFieldValue('role') as Role | undefined
              return role ? (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {ROLE_HINTS[role]}
                </Typography.Text>
              ) : null
            }}
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 6, message: '密码至少 6 位' }]}>
            <Input.Password placeholder="至少 6 位" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认密码"
            dependencies={['password']}
            rules={[
              { required: true, message: '请再次输入密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) return Promise.resolve()
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password placeholder="再次输入密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block size="large">
            注册
          </Button>
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Typography.Text type="secondary">已有账号？</Typography.Text>{' '}
            <Link to="/login">去登录</Link>
          </div>
        </Form>
      </Card>
    </div>
  )
}
