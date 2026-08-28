<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">排班管理</h2>
      <div class="spacer"></div>
      <template v-if="auth.role === 'admin'">
        <span class="filter-label">人员</span>
        <el-select
          v-model="staffId"
          placeholder="全部人员"
          clearable
          filterable
          style="width: 160px"
        >
          <el-option v-for="s in staffOptions" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </template>
      <el-button type="primary" :icon="'Plus'" @click="openCreate">新建排班</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="staff_name" label="人员" min-width="100" />
        <el-table-column prop="staff_role" label="角色" width="80">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ ROLE_LABELS[row.staff_role] || row.staff_role }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="work_date" label="日期" width="120" />
        <el-table-column label="班次" width="90">
          <template #default="{ row }">
            <el-tag :type="shiftStatus(row.shift).type" size="small">
              {{ shiftStatus(row.shift).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="department" label="科室" min-width="100">
          <template #default="{ row }">{{ row.department || '-' }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remark || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="scheduleStatus(row.status).type" size="small">
              {{ scheduleStatus(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pager"
        layout="total, prev, pager, next"
        :total="total"
        :page-size="query.size"
        :current-page="query.page"
        @current-change="(p) => load(p)"
      />
    </el-card>

    <!-- 新建排班 -->
    <el-dialog v-model="dialogVisible" title="新建排班" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="人员" required>
          <el-select v-model="form.staff_id" placeholder="选择人员" filterable style="width: 100%">
            <el-option v-for="s in staffOptions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期" required>
          <el-date-picker
            v-model="form.work_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="排班日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="班次" required>
          <el-radio-group v-model="form.shift">
            <el-radio value="day">早班</el-radio>
            <el-radio value="evening">中班</el-radio>
            <el-radio value="night">夜班</el-radio>
            <el-radio value="off">休息</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="科室">
          <el-select v-model="form.department" placeholder="可选" clearable filterable style="width: 100%">
            <el-option v-for="d in DEPARTMENTS" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="备注信息（可选）" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="在岗" value="on_duty" />
            <el-option label="休班" value="off" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { medicalApi, authApi, ROLE_LABELS } from '@/api'
import type { Schedule } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { pickStatus, SCHEDULE_SHIFTS, SCHEDULE_STATUS, DEPARTMENTS } from '@/utils/constants'

const auth = useAuthStore()

const loading = ref(false)
const saving = ref(false)
const list = ref<Schedule[]>([])
const total = ref(0)
const query = reactive({ page: 1, size: 10 })
const staffId = ref<number | undefined>(undefined)
const staffOptions = ref<{ id: number; name: string }[]>([])

const dialogVisible = ref(false)
const form = reactive<Partial<Schedule>>({
  staff_id: undefined,
  work_date: '',
  shift: 'day',
  department: '',
  remark: '',
  status: 'on_duty',
})

/** 可排班人员：admin 读取医生/护士用户表；医生默认自己 */
async function loadStaffOptions() {
  if (auth.role === 'admin') {
    try {
      const [doctors, nurses] = await Promise.all([
        authApi.listUsers({ role: 'doctor', size: 1000 }),
        authApi.listUsers({ role: 'nurse', size: 1000 }),
      ])
      staffOptions.value = [
        ...(doctors.list || []).map((u) => ({ id: u.id, name: u.display_name || u.username })),
        ...(nurses.list || []).map((u) => ({ id: u.id, name: u.display_name || u.username })),
      ]
    } catch {
      staffOptions.value = []
    }
  } else {
    staffOptions.value = [{ id: auth.user?.id || 0, name: auth.user?.display_name || '' }]
  }
}

async function load(page = 1) {
  loading.value = true
  query.page = page
  try {
    const params: Record<string, unknown> = { page: query.page, size: query.size }
    if (auth.role === 'admin' && staffId.value) params.staff_id = staffId.value
    const res = await medicalApi.listSchedules(params)
    list.value = res.list || []
    total.value = res.total
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, {
    staff_id: auth.role === 'doctor' ? auth.user?.id : undefined,
    work_date: '',
    shift: 'day',
    department: '',
    remark: '',
    status: 'on_duty',
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.staff_id) {
    ElMessage.warning('请选择人员')
    return
  }
  if (!form.work_date || !form.shift) {
    ElMessage.warning('日期和班次不能为空')
    return
  }
  saving.value = true
  try {
    await medicalApi.createSchedule({ ...form })
    ElMessage.success('创建成功')
    dialogVisible.value = false
    load(query.page)
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

function shiftStatus(s?: string) {
  return pickStatus(SCHEDULE_SHIFTS, s)
}
function scheduleStatus(s?: string) {
  return pickStatus(SCHEDULE_STATUS, s)
}

onMounted(() => {
  loadStaffOptions()
  load(1)
})
</script>

<style scoped>
.filter-label {
  font-size: 13px;
  color: #909399;
}

.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
</style>
