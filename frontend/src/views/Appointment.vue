<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">预约挂号</h2>
      <div class="spacer"></div>
      <template v-if="canViewAll">
        <span class="filter-label">患者</span>
        <el-select
          v-model="patientId"
          placeholder="全部患者"
          clearable
          filterable
          style="width: 160px"
        >
          <el-option v-for="p in patientOptions" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </template>
      <el-button type="primary" :icon="'Plus'" @click="openCreate">预约挂号</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="patient_name" label="患者" min-width="80" />
        <el-table-column prop="department" label="科室" min-width="90" />
        <el-table-column prop="doctor_name" label="医生" min-width="80">
          <template #default="{ row }">{{ row.doctor_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="date" label="日期" width="110" />
        <el-table-column prop="time_slot" label="时间段" width="120" />
        <el-table-column prop="symptom" label="症状" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ row.symptom || '-' }}</template>
        </el-table-column>
        <el-table-column prop="fee" label="费用" width="90" align="right">
          <template #default="{ row }">¥{{ Number(row.fee || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="apptStatus(row.status).type" size="small">
              {{ apptStatus(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <template v-if="canManage">
              <el-button v-if="row.status !== 'cancelled'" link type="primary" size="small" @click="openEdit(row)">
                处理
              </el-button>
              <el-button
                v-if="row.status === 'booked'"
                link
                type="danger"
                size="small"
                @click="updateStatus(row, 'cancelled')"
              >
                取消
              </el-button>
            </template>
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

    <!-- 新建/编辑预约 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '处理预约' : '预约挂号'"
      width="520px"
    >
      <el-form :model="form" label-width="80px">
        <el-form-item v-if="canViewAll" label="患者" required>
          <el-select v-model="form.patient_id" placeholder="选择患者" filterable style="width: 100%">
            <el-option v-for="p in patientOptions" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="科室" required>
          <el-select v-model="form.department" placeholder="选择科室" style="width: 100%">
            <el-option v-for="d in DEPARTMENTS" :key="d" :label="d" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期" required>
          <el-date-picker
            v-model="form.date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            :disabled-date="disabledDate"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="时间段" required>
          <el-select v-model="form.time_slot" placeholder="选择时间段" style="width: 100%">
            <el-option v-for="t in TIME_SLOTS" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="医生">
          <el-select v-model="form.doctor_id" placeholder="选择医生（可选）" clearable filterable style="width: 100%">
            <el-option v-for="d in doctorOptions" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="症状">
          <el-input v-model="form.symptom" type="textarea" :rows="2" placeholder="简单描述症状" />
        </el-form-item>
        <el-form-item label="费用">
          <el-input-number v-model="form.fee" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="editing" label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="已预约" value="booked" />
            <el-option label="已确认" value="confirmed" />
            <el-option label="已就诊" value="visited" />
            <el-option label="已取消" value="cancelled" />
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
import {computed, onMounted, reactive, ref} from 'vue'
import {ElMessage} from 'element-plus'
import {getDoctorOptions, getPatientOptions, medicalApi} from '@/api'
import type {Appointment} from '@/types'
import {useAuthStore} from '@/stores/auth'
import {APPOINTMENT_STATUS, DEPARTMENTS, pickStatus, TIME_SLOTS} from '@/utils/constants'

const auth = useAuthStore()
const canViewAll = computed(() => ['doctor', 'admin'].includes(auth.role))
const canManage = computed(() => ['doctor', 'admin'].includes(auth.role))

const loading = ref(false)
const saving = ref(false)
const list = ref<Appointment[]>([])
const total = ref(0)
const query = reactive({ page: 1, size: 10 })
const patientId = ref<number | undefined>(undefined)

const patientOptions = ref<{ id: number; name: string }[]>([])
const doctorOptions = ref<{ id: number; name: string }[]>([])

const dialogVisible = ref(false)
const editing = ref(false)
const form = reactive<Partial<Appointment>>({
  patient_id: undefined,
  doctor_id: undefined,
  department: '',
  date: '',
  time_slot: '',
  symptom: '',
  fee: 0,
  status: 'booked',
})

async function load(page = 1) {
  loading.value = true
  query.page = page
  try {
    const params: Record<string, unknown> = { page: query.page, size: query.size }
    if (canViewAll.value && patientId.value) params.patient_id = patientId.value
    const res = await medicalApi.listAppointments(params)
    list.value = res.list || []
    total.value = res.total
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = false
  Object.assign(form, {
    patient_id: undefined,
    doctor_id: undefined,
    department: '',
    date: '',
    time_slot: '',
    symptom: '',
    fee: 0,
    status: 'booked',
  })
  dialogVisible.value = true
}

function openEdit(row: Appointment) {
  editing.value = true
  Object.assign(form, {
    patient_id: row.patient_id,
    doctor_id: row.doctor_id,
    department: row.department,
    date: row.date,
    time_slot: row.time_slot,
    symptom: row.symptom,
    fee: row.fee,
    status: row.status,
  })
  ;(form as Appointment).id = row.id
  dialogVisible.value = true
}

async function save() {
  if (!form.department || !form.date || !form.time_slot) {
    ElMessage.warning('科室、日期和时间段不能为空')
    return
  }
  if (canViewAll.value && !form.patient_id) {
    ElMessage.warning('请选择患者')
    return
  }
  saving.value = true
  try {
    if (editing.value && form.id) {
      await medicalApi.updateAppointment(form.id, { ...form })
      ElMessage.success('更新成功')
    } else {
      await medicalApi.createAppointment({ ...form })
      ElMessage.success('预约成功')
    }
    dialogVisible.value = false
    load(query.page)
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function updateStatus(row: Appointment, status: string) {
  try {
    await medicalApi.updateAppointment(row.id, { status })
    ElMessage.success('操作成功')
    load(query.page)
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '操作失败')
  }
}

function apptStatus(s?: string) {
  return pickStatus(APPOINTMENT_STATUS, s)
}

function disabledDate(date: Date) {
  return date.getTime() < Date.now() - 86400000
}

onMounted(async () => {
  if (canViewAll.value) {
    patientOptions.value = await getPatientOptions(auth.role)
    doctorOptions.value = await getDoctorOptions(
      auth.role,
      auth.user?.id,
      auth.user?.display_name,
    )
  }
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
