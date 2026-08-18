<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">🏥 医智助手</div>
      <el-menu :default-active="activeMenu" router class="menu" background-color="#001529" text-color="#ffffff80"
               active-text-color="#fff">
        <el-menu-item v-for="item in menus" :key="item.path" :index="item.path">
          <el-icon>
            <component :is="item.icon"/>
          </el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span class="header-title">医智助手 · 医疗知识库智能问答</span>
        <span v-if="auth.user" class="header-right">
          <el-tag :type="ROLE_TAG_TYPES[auth.user.role]" size="default">
            {{ ROLE_LABELS[auth.user.role] }} · {{ auth.user.display_name }}
          </el-tag>
          <el-link type="danger" :underline="false" @click="logout">
            <el-icon><SwitchButton/></el-icon>&nbsp;退出登录
          </el-link>
        </span>
      </el-header>

      <el-main class="main">
        <router-view/>
      </el-main>

      <el-footer class="footer">
        © {{ year }} All Rights Reserved · 医智助手医疗信息系统教学演示平台 · 内容仅用于健康科普，不构成诊疗建议
      </el-footer>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import {computed} from 'vue'
import {useRoute, useRouter} from 'vue-router'
import {useAuth} from '../stores/auth'
import type {Role} from '../types'
import {ROLE_LABELS, ROLE_TAG_TYPES} from '../types'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const year = new Date().getFullYear()

interface MenuItem {
  path: string
  label: string
  icon: string
}

const COMMON_MENU: MenuItem[] = [
  {path: '/', label: '数据仪表盘', icon: 'Odometer'},
  {path: '/chat', label: '智能咨询', icon: 'ChatDotRound'},
  {path: '/chat/history', label: '咨询历史', icon: 'Clock'},
]

const ROLE_MENUS: Record<Role, MenuItem[]> = {
  patient: [
    ...COMMON_MENU,
    {path: '/patient', label: '我的健康档案', icon: 'Files'},
    {path: '/appointments', label: '预约挂号', icon: 'Calendar'},
  ],
  doctor: [
    ...COMMON_MENU,
    {path: '/doctor/patients', label: '患者管理', icon: 'User'},
    {path: '/doctor/hospitalizations', label: '住院信息管理', icon: 'FirstAidKit'},
    {path: '/schedule', label: '排班管理', icon: 'Calendar'},
    {path: '/kb', label: '知识库管理', icon: 'Collection'},
    {path: '/doctor', label: '医生工作台', icon: 'Monitor'},
  ],
  nurse: [
    ...COMMON_MENU,
    {path: '/nurse', label: '护理工作台', icon: 'Document'},
    {path: '/schedule', label: '排班管理', icon: 'Calendar'},
  ],
  public: [
    ...COMMON_MENU,
    {path: '/health', label: '健康资讯', icon: 'Reading'},
    {path: '/guide', label: '就诊指南', icon: 'Compass'},
    {path: '/appointments', label: '预约挂号', icon: 'Calendar'},
  ],
  admin: [
    ...COMMON_MENU,
    {path: '/admin', label: '系统管理', icon: 'Setting'},
    {path: '/kb', label: '知识库管理', icon: 'Collection'},
  ],
}

const menus = computed<MenuItem[]>(() => {
  if (!auth.user) return COMMON_MENU
  return ROLE_MENUS[auth.user.role] ?? COMMON_MENU
})

// 修复：/chat/history 与 /chat/history/:id 高亮"咨询历史"
const activeMenu = computed(() => {
  const path = route.path
  if (path === '/') return '/'
  const matches = menus.value.filter(
      (i) => i.path !== '/' && (path === i.path || path.startsWith(i.path + '/')),
  )
  matches.sort((a, b) => b.path.length - a.path.length)
  return matches.length ? matches[0].path : path
})

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
}

.aside {
  background: #001529;
  overflow: auto;
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
}

.menu {
  border-right: none;
}

.header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}

.header-title {
  font-size: 16px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.main {
  margin: 16px;
  background: transparent;
}

.footer {
  text-align: center;
  color: #999;
  background: #fff;
  border-top: 1px solid #f0f0f0;
}
</style>