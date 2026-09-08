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
              <el-avatar :size="30" :class="['user-avatar', `role-${auth.role}`]">
                <el-icon><component :is="roleIcon" /></el-icon>
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
import { UserFilled, FirstAidKit, User, Setting } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import SideMenu from './SideMenu.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const isMobile = ref(false)
const drawerVisible = ref(false)

// 角色 → 图标映射（使用 Element Plus 实际存在的图标）
const ROLE_ICONS: Record<string, any> = {
  patient: UserFilled,   // 患者：实心人形
  doctor: UserFilled,    // 医生：实心人形（用颜色区分）
  nurse: FirstAidKit,    // 护士：急救箱
  public: User,          // 群众：空心人形
  admin: Setting,        // 管理员：设置
}

const roleIcon = computed(() => ROLE_ICONS[auth.role] || UserFilled)

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

/* 角色头像颜色 */
.user-avatar.role-patient {
  background: #409eff;  /* 患者：蓝色 */
}
.user-avatar.role-doctor {
  background: #67c23a;  /* 医生：绿色 */
}
.user-avatar.role-nurse {
  background: #e6a23c;  /* 护士：橙色 */
}
.user-avatar.role-public {
  background: #909399;  /* 群众：灰色 */
}
.user-avatar.role-admin {
  background: #9c27b0;  /* 管理员：紫色 */
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
