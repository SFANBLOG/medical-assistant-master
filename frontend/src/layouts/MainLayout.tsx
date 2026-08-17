import { Layout, Menu, Space, Tag, Typography } from 'antd'
import type { MenuProps } from 'antd'
import {
  CalendarOutlined,
  CompassOutlined,
  ControlOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  HistoryOutlined,
  HomeOutlined,
  LogoutOutlined,
  MedicineBoxOutlined,
  MessageOutlined,
  ReadOutlined,
  ScheduleOutlined,
  SettingOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useMemo } from 'react'
import { useAuth } from '../stores/auth'
import { ROLE_COLORS, ROLE_LABELS } from '../types'
import type { Role } from '../types'

const { Header, Sider, Content, Footer } = Layout
type MenuItem = Required<MenuProps>['items'][number]

const COMMON_MENU: MenuItem[] = [
  { key: '/', icon: <DashboardOutlined />, label: '数据仪表盘' },
  { key: '/chat', icon: <MessageOutlined />, label: '智能咨询' },
  { key: '/chat/history', icon: <HistoryOutlined />, label: '咨询历史' },
]

const ROLE_MENUS: Record<Role, MenuItem[]> = {
  patient: [
    ...COMMON_MENU,
    { key: '/patient', icon: <HomeOutlined />, label: '我的健康档案' },
    { key: '/appointments', icon: <CalendarOutlined />, label: '预约挂号' },
  ],
  doctor: [
    ...COMMON_MENU,
    { key: '/doctor/patients', icon: <TeamOutlined />, label: '患者管理' },
    { key: '/doctor/hospitalizations', icon: <MedicineBoxOutlined />, label: '住院信息管理' },
    { key: '/schedule', icon: <ScheduleOutlined />, label: '排班管理' },
    { key: '/kb', icon: <DatabaseOutlined />, label: '知识库管理' },
    { key: '/doctor', icon: <ControlOutlined />, label: '医生工作台' },
  ],
  nurse: [
    ...COMMON_MENU,
    { key: '/nurse', icon: <FileTextOutlined />, label: '护理工作台' },
    { key: '/schedule', icon: <ScheduleOutlined />, label: '排班管理' },
  ],
  public: [
    ...COMMON_MENU,
    { key: '/health', icon: <ReadOutlined />, label: '健康资讯' },
    { key: '/guide', icon: <CompassOutlined />, label: '就诊指南' },
    { key: '/appointments', icon: <CalendarOutlined />, label: '预约挂号' },
  ],
  admin: [
    ...COMMON_MENU,
    { key: '/admin', icon: <SettingOutlined />, label: '系统管理' },
    { key: '/kb', icon: <DatabaseOutlined />, label: '知识库管理' },
  ],
}

export default function MainLayout() {
  const user = useAuth((s) => s.user)
  const logout = useAuth((s) => s.logout)
  const navigate = useNavigate()
  const location = useLocation()

  const items = useMemo(() => {
    if (!user) return COMMON_MENU
    return ROLE_MENUS[user.role] ?? COMMON_MENU
  }, [user])

  // 修复：/chat/history 与 /chat/history/:id 应高亮“咨询历史”而非“智能咨询”
  const selected = useMemo(() => {
    const path = location.pathname
    if (path === '/') return '/'
    const matches = items.filter(
      (i) => i && typeof i === 'object' && 'key' in i && i.key !== '/' &&
        (path === i.key || path.startsWith(String(i.key) + '/')),
    )
    matches.sort((a, b) => String((b as { key: string }).key).length - String((a as { key: string }).key).length)
    return matches.length ? String((matches[0] as { key: string }).key) : path
  }, [items, location.pathname])

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="dark" width={220}>
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: 18,
            fontWeight: 600,
          }}
        >
          🏥 医智助手
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={items}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,21,41,0.08)',
          }}
        >
          <Typography.Text strong style={{ fontSize: 16 }}>
            医智助手 · 医疗知识库智能问答
          </Typography.Text>
          <Space size="middle">
            {user && (
              <>
                <Tag color={ROLE_COLORS[user.role]}>
                  {ROLE_LABELS[user.role]} · {user.display_name}
                </Tag>
                <Typography.Link
                  onClick={() => {
                    logout()
                    navigate('/login')
                  }}
                >
                  <LogoutOutlined /> 退出登录
                </Typography.Link>
              </>
            )}
          </Space>
        </Header>
        <Content style={{ margin: 16 }}>
          <Outlet />
        </Content>
        <Footer
          style={{
            textAlign: 'center',
            color: '#999',
            padding: '16px 24px',
            background: '#fff',
            borderTop: '1px solid #f0f0f0',
          }}
        >
          © {new Date().getFullYear()} 安徽医科大学 · 医智助手医疗信息系统教学演示平台 · 内容仅用于健康科普，不构成诊疗建议
        </Footer>
      </Layout>
    </Layout>
  )
}
