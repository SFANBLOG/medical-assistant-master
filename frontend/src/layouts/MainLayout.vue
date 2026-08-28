<template>
  <el-container class="layout">
    <!-- 桌面端侧边栏 -->
    <el-aside v-if="!isMobile" width="220px" class="aside">
      <SideMenu :active-menu="activeMenu" @navigate="onNavigate" />
    </el-aside>

    <!-- 移动端抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      direction="ltr"
      size="230px"
      :with-header="false"
      class="mobile-drawer"
    >
      <SideMenu :active-menu="activeMenu" @navigate="onNavigate" />
    </el-drawer>

    <el-container class="main-container">
      <!-- 顶栏 -->
      <el-header class="header" height="56px">
        <div class="header-left">
          <el-button
            v-if="isMobile"
            class="menu-btn"
            text
            @click="drawerVisible = true"
          >
            <el-icon :size="20"><Menu /></el-icon>
          </el-button>
          <span class="page-title">{{ pageTitle }}</span>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="30" class="user-avatar">
                <el-icon><UserFilled /></el-icon>
              </el-avatar>
              <span class="user-name">{{ auth.user?.display_name || auth.user?.username }}</span>
              <el-tag size="small" :class="roleTagClass">{{ auth.roleLabel }}</el-tag>
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  账号：{{ auth.user?.username }}
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import SideMenu from './SideMenu.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const isMobile = ref(false)
const drawerVisible = ref(false)

function checkMobile() {
  isMobile.value = window.innerWidth < 992
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', checkMobile)
})

const activeMenu = computed(() => route.path)

const pageTitle = computed(() => (route.meta.title as string) || '医智助手')

const roleTagClass = computed(() => `role-tag-${auth.role || 'public'}`)

function onNavigate() {
  drawerVisible.value = false
}

async function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning' })
    } catch {
      return
    }
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.layout {
  height: 100vh;
  overflow: hidden;
}

.aside {
  background: #fff;
  border-right: 1px solid var(--el-border-color-light);
  display: flex;
  flex-direction: column;
}

.main-container {
  min-width: 0;
}

.header {
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.menu-btn {
  padding: 4px;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
}

.user-avatar {
  background: var(--el-color-primary);
  color: #fff;
}

.user-name {
  font-size: 14px;
  color: #303133;
}

.content {
  padding: 0;
  overflow-y: auto;
  background: var(--med-bg);
}

.mobile-drawer :deep(.el-drawer__body) {
  padding: 0;
}
</style>
