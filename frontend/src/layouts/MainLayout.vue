<template>
  <el-container class="layout">
    <el-aside width="232px" class="aside">
      <div class="logo">
        <span class="logo-icon">🏥</span>
        <div class="logo-text">
          <div class="logo-title">医智助手</div>
          <div class="logo-sub">医疗知识库智能问答</div>
        </div>
      </div>
      <div class="role-badge" v-if="auth.user">
        <el-tag :type="ROLE_TAG_TYPES[auth.user.role]" effect="plain" round size="small">
          {{ ROLE_LABELS[auth.user.role] }}
        </el-tag>
        <span class="role-name">{{ auth.user.display_name }}</span>
      </div>
      <el-menu :default-active="activeMenu" router class="menu" background-color="#ffffff" text-color="#4b5563"
               active-text-color="#1d4ed8">
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
        <span class="header-title">复旦医学院智慧医疗教学平台 · {{ pageTitle }}</span>
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
        © {{ year }} All Rights Reserved · 复旦医学院智慧医疗信息系统教学演示平台 · 内容仅用于健康科普，不构成诊疗建议
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

const ROLE_MENUS: Record<Role, MenuItem[]> = {
  admin: [
    {path: '/', label: '数据仪表盘', icon: 'Odometer'},
    {path: '/chat', label: '智能咨询', icon: 'ChatDotRound'},
    {path: '/chat/history', label: '咨询历史', icon: 'Clock'},
    {path: '/kb', label: '知识库管理', icon: 'Collection'},
    {path: '/admin', label: '系统管理 / 用户管理', icon: 'Setting'},
  ],
  doctor: [
    {path: '/chat', label: '智能咨询', icon: 'ChatDotRound'},
    {path: '/chat/history', label: '咨询历史', icon: 'Clock'},
    {path: '/kb', label: '知识库管理', icon: 'Collection'},
    {path: '/health', label: '患者教育', icon: 'Reading'},
  ],
  nurse: [
    {path: '/chat', label: '智能咨询', icon: 'ChatDotRound'},
    {path: '/chat/history', label: '咨询历史', icon: 'Clock'},
    {path: '/kb', label: '知识库查看', icon: 'Collection'},
  ],
  patient: [
    {path: '/chat', label: '智能咨询', icon: 'ChatDotRound'},
    {path: '/chat/history', label: '咨询历史', icon: 'Clock'},
    {path: '/kb', label: '知识库查看', icon: 'Collection'},
  ],
  public: [
    {path: '/chat', label: '智能咨询', icon: 'ChatDotRound'},
    {path: '/chat/history', label: '咨询历史', icon: 'Clock'},
    {path: '/kb', label: '知识库查看', icon: 'Collection'},
  ],
}

const menus = computed<MenuItem[]>(() => {
  if (!auth.user) return ROLE_MENUS.public
  return ROLE_MENUS[auth.user.role] ?? ROLE_MENUS.public
})

const pageTitle = computed(() => {
  const item = menus.value.find((m) => m.path === activeMenu.value)
  return item?.label ?? '工作台'
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
  background: #ffffff;
  overflow: auto;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.04);
  border-right: 1px solid #e8eef5;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  color: #1d4ed8;
  border-bottom: 1px solid #e8eef5;
}

.logo-icon {
  font-size: 28px;
  margin-right: 12px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eff6ff;
  border-radius: 8px;
}

.logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.logo-title {
  font-size: 17px;
  font-weight: 700;
  color: #1d4ed8;
  letter-spacing: 0.5px;
}

.logo-sub {
  font-size: 11px;
  color: #6b7280;
  font-weight: 400;
}

.role-badge {
  padding: 14px 16px;
  border-bottom: 1px solid #f0f5fa;
  display: flex;
  align-items: center;
  gap: 10px;
}

.role-name {
  font-size: 14px;
  color: #374151;
  font-weight: 500;
}

.menu {
  border-right: none;
  padding-top: 8px;
}

.menu :deep(.el-menu-item) {
  height: 48px;
  line-height: 48px;
  margin: 0 10px 4px;
  padding-left: 14px !important;
  border-radius: 8px;
  font-size: 14px;
  transition: all 0.2s;
}

.menu :deep(.el-menu-item:hover) {
  background: #eff6ff;
  color: #1d4ed8;
}

.menu :deep(.el-menu-item.is-active) {
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
  border-left: 3px solid #1d4ed8;
  padding-left: 11px !important;
}

.menu :deep(.el-icon) {
  color: inherit;
  margin-right: 10px;
  font-size: 18px;
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
  color: #1e3a8a;
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