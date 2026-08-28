<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">住院信息管理</h2>
      <div class="spacer"></div>
      <el-input
        v-model="searchText"
        placeholder="搜索患者姓名"
        clearable
        :prefix-icon="'Search'"
        style="width: 180px"
      />
      <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 120px">
        <el-option label="住院中" value="in_hospital" />
        <el-option label="已出院" value="discharged" />
      </el-select>
      <el-button type="primary" :icon="'Plus'" @click="openCreate">新建住院记录</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="filteredList" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="patient_name" label="患者" min-width="90" />
        <el-table-column prop="department" label="科室" min-width="90" />
        <el-table-column prop="ward" label="病房" width="80">
          <template #default="{ row }">{{ row.ward || '-' }}</template>
        </el-table-column>
        <el-table-column prop="bed_no" label="床号" width="70">
          <template #default="{ row }">{{ row.bed_no || '-' }}</template>
        </el-table-column>
        <el-table-column prop="diagnosis" label="诊断" min-width="150" show-overflow-tooltip />
        <el-table-column prop="admit_date" label="入院日期" width="110" />
        <el-table-column prop="discharge_date" label="出院日期" width="110">
          <template #default="{ row }">{{ row.discharge_date || '-' }}</template>
        </el-table-column>
        <el-table-column prop="doctor_name" label="主治医生" min-width="90" />
        <el-table-column prop="total_cost" label="费用" width="100" align="right">
          <template #default="{ row }">¥{{ Number(row.total_cost || 0).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="hospStatus(row.status).type" size="small">
              {{ hospStatus(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
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

    <!-- 新建/编辑住院记录 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑住院记录' : '新建住院记录'"
      width="560px"
    >
      <el-form :model="form" label-width="90px">
        <el-form-item label="患者" required>
          <el-select
            v-model="form.patient_id"
            placeholder="选择患者"
            filterable
            style="width: 100%"
            :disabled="editing"
          >
            <el-option v-for="p in patientOptions" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="入院日期" required>
              <el-date-picker
                v-model="form.admit_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="入院日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="出院日期">
              <el-date-picker
                v-model="form.discharge_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="可选"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="科室" required>
              <el-select v-model="form.department" placeholder="科室" filterable style="width: 100%">
                <el-option v-for="d in DEPARTMENTS" :key="d" :label="d" :value="d" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="主治医生">
              <el-select v-model="form.doctor_id" placeholder="可选" clearable filterable style="width: 100%">
                <el-option v-for="d in doctorOptions" :key="d.id" :label="d.name" :value="d.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="病房">
              <el-input v-model="form.ward" placeholder="如：A区302" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="床号">
              <el-input v-model="form.bed_no" placeholder="如：3床" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="诊断">
          <el-input v-model="form.diagnosis" type="textarea" :rows="2" placeholder="诊断结果" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option label="住院中" value="in_hospital" />
                <el-option label="已出院" value="discharged" />
                <el-option label="已转院" value="transferred" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="总费用">
              <el-input-number v-model="form.total_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { medicalApi, getPatientOptions, getDoctorOptions } from '@/api'
import type { Hospitalization } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { pickStatus, HOSPITAL_STATUS, DEPARTMENTS } from '@/utils/constants'

const auth = useAuthStore()

const loading = ref(false)
const saving = ref(false)
const list = ref<Hospitalization[]>([])
const total = ref(0)
const query = reactive({ page: 1, size: 50 })
const searchText = ref('')
const statusFilter = ref('')

const patientOptions = ref<{ id: number; name: string }[]>([])
const doctorOptions = ref<{ id: number; name: string }[]>([])

const dialogVisible = ref(false)
const editing = ref(false)
const form = reactive<Partial<Hospitalization> & { id?: number }>({
  patient_id: undefined,
  admit_date: '',
  discharge_date: '',
  department: '',
  ward: '',
  bed_no: '',
  diagnosis: '',
  doctor_id: undefined,
  status: 'in_hospital',
  total_cost: 0,
})

const filteredList = computed(() => {
  const kw = searchText.value.trim()
  if (!kw && !statusFilter.value) return list.value
  return list.value.filter((row) => {
    const matchKw = !kw || (row.patient_name || '').includes(kw)
    const matchStatus = !statusFilter.value || row.status === statusFilter.value
    return matchKw && matchStatus
  })
})

async function load(page = 1) {
  loading.value = true
  query.page = page
  try {
    const res = await medicalApi.listHospitalizations({ page: query.page, size: query.size })
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
    admit_date: '',
    discharge_date: '',
    department: '',
    ward: '',
    bed_no: '',
    diagnosis: '',
    doctor_id: undefined,
    status: 'in_hospital',
    total_cost: 0,
  })
  dialogVisible.value = true
}

function openEdit(row: Hospitalization) {
  editing.value = true
  Object.assign(form, {
    id: row.id,
    patient_id: row.patient_id,
    admit_date: row.admit_date,
    discharge_date: row.discharge_date || '',
    department: row.department,
    ward: row.ward || '',
    bed_no: row.bed_no || '',
    diagnosis: row.diagnosis || '',
    doctor_id: row.doctor_id,
    status: row.status,
    total_cost: row.total_cost,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.patient_id) {
    ElMessage.warning('请选择患者')
    return
  }
  if (!form.admit_date || !form.department) {
    ElMessage.warning('入院日期和科室不能为空')
    return
  }
  saving.value = true
  try {
    if (editing.value && form.id) {
      await medicalApi.updateHospitalization(form.id, { ...form })
      ElMessage.success('更新成功')
    } else {
      await medicalApi.createHospitalization({ ...form })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    load(query.page)
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

function hospStatus(s?: string) {
  return pickStatus(HOSPITAL_STATUS, s)
}

onMounted(async () => {
  patientOptions.value = await getPatientOptions(auth.role)
  doctorOptions.value = await getDoctorOptions(
    auth.role,
    auth.user?.id,
    auth.user?.display_name,
  )
  load(1)
})
</script>

<style scoped>
.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
</style>
