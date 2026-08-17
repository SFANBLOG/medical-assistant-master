import { Button, Card, Form, Input, App, Typography } from 'antd'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../stores/auth'

interface FormValues {
  username: string
  password: string
}

export default function LoginPage() {
  const login = useAuth((s) => s.login)
  const navigate = useNavigate()
  const { message } = App.useApp()

  const onFinish = async (values: FormValues) => {
    try {
      await login(values.username, values.password)
      message.success('登录成功')
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
      <Card style={{ width: 380, boxShadow: '0 8px 24px rgba(0,0,0,0.08)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 40 }}>🏥</div>
          <Typography.Title level={3} style={{ marginTop: 8, marginBottom: 4 }}>
            医智助手
          </Typography.Title>
          <Typography.Text type="secondary">医疗知识库智能问答系统</Typography.Text>
        </div>
        <Form<FormValues> layout="vertical" onFinish={onFinish}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input placeholder="演示账号：patientdemo / doctordemo / admindemo" autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password placeholder="演示密码：demo123" autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block size="large">
            登录
          </Button>
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Typography.Text type="secondary">还没有账号？</Typography.Text>{' '}
            <Link to="/register">立即注册</Link>
          </div>
        </Form>
      </Card>
    </div>
  )
}
