<template>
  <div class="side-menu">
    <div class="logo" @click="$router.push('/dashboard')">
      <div class="logo-icon">
        <el-icon :size="22"><FirstAidKit /></el-icon>
      </div>
      <div class="logo-text">
        <span class="name">医智助手</span>
        <span class="sub">智能医疗问答</span>
      </div>
    </div>

    <el-scrollbar class="menu-scroll">
      <el-menu
        :default-active="activeMenu"
        :collapse="false"
        router
        class="menu"
      >
        <template v-for="group in menuGroups" :key="group.title">
          <div class="menu-group-title">{{ group.title }}</div>
          <el-menu-item
            v-for="item in group.items"
            :key="item.path"
            :index="item.path"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import {computed} from 'vue'
import {useAuthStore} from '@/stores/auth'

defineProps<{ activeMenu: string }>()

const auth = useAuthStore()
const role = computed(() => auth.role)

const menuGroups = computed(() => {
  const r = role.value
  const groups: { title: string; items: { path: string; title: string; icon: string }[] }[] =
    [
      {
        title: '通用功能',
        items: [
          { path: '/dashboard', title: '数据仪表盘', icon: 'Odometer' },
          { path: '/chat', title: '智能咨询', icon: 'ChatDotRound' },
          { path: '/chat/history', title: '咨询历史', icon: 'History' },
          { path: '/health-records', title: '健康档案', icon: 'Files' },
          { path: '/appointment', title: '预约挂号', icon: 'Calendar' },
          { path: '/health-info', title: '健康资讯', icon: 'Reading' },
          { path: '/guide', title: '就诊指南', icon: 'Compass' },
        ],
      },
    ]

  if (r === 'doctor' || r === 'admin') {
    groups.push({
      title: '医疗管理',
      items: [
        { path: '/doctor/patients', title: '患者管理', icon: 'User' },
        { path: '/doctor/hospitalization', title: '住院信息管理', icon: 'FirstAidKit' },
        { path: '/doctor/schedules', title: '排班管理', icon: 'Clock' },
        { path: '/kb', title: '知识库管理', icon: 'Collection' },
      ],
    })
  }

  if (r === 'nurse') {
    groups.push({
      title: '护理管理',
      items: [
        { path: '/nurse', title: '护理工作台', icon: 'FirstAidKit' },
      ],
    })
  }

  if (r === 'admin') {
    groups.push({
      title: '系统管理',
      items: [
        { path: '/admin/users', title: '系统用户管理', icon: 'Setting' },
        { path: '/admin/system', title: '全系统数据看板', icon: 'Monitor' },
      ],
    })
  }

  return groups
})
</script>

<style scoped>
.side-menu {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.logo-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(135deg, #409eff, #79bbff);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.logo-text .name {
  font-size: 16px;
  font-weight: 700;
  color: #303133;
}

.logo-text .sub {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.menu-scroll {
  flex: 1;
}

.menu {
  border-right: none;
}

.menu-group-title {
  font-size: 12px;
  color: #909399;
  padding: 12px 20px 4px;
}

.menu :deep(.el-menu-item) {
  height: 44px;
}

.menu :deep(.el-menu-item.is-active) {
  background: #ecf5ff;
  border-right: 3px solid #409eff;
  color: #409eff;
}
</style>
