<template>
  <el-card>
    <template #header>
      <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px">
        <span>住院信息管理</span>
        <el-button type="primary" @click="openModal"><el-icon><Plus /></el-icon>&nbsp;新增住院</el-button>
      </div>
    </template>

    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap">
      <el-radio-group v-model="status">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="in_hospital">在院</el-radio-button>
        <el-radio-button value="discharged">已出院</el-radio-button>
      </el-radio-group>
      <span style="color: #999">共 {{ items.length }} 条记录</span>
    </div>

    <el-table :data="items" v-loading="loading" size="small" row-key="id">
      <el-table-column label="患者" width="110">
        <template #default="{ row }">{{ row.patient_name || row.patient_username || `#${row.patient_id}` }}</template>
      </el-table-column>
      <el-table-column label="入院日期" prop="admit_date" width="115" />
      <el-table-column label="出院日期" width="115">
        <template #default="{ row }">{{ row.discharge_date || '-' }}</template>
      </el-table-column>
      <el-table-column label="科室" prop="department" width="100" />
      <el-table-column label="病床" width="90">
        <template #default="{ row }">{{ [row.ward, row.bed_no].filter(Boolean).join(' ') || '-' }}</template>
      </el-table-column>
      <el-table-column label="诊断" prop="diagnosis" min-width="130" show-overflow-tooltip />
      <el-table-column label="主治医生" width="100">
        <template #default="{ row }">{{ row.doctor_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.status === 'in_hospital'" type="primary">在院</el-tag>
          <el-tag v-else type="info">已出院</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="费用(元)" width="110" align="right">
        <template #default="{ row }">{{ Number(row.total_cost).toLocaleString('zh-CN') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button v-if="row.status === 'in_hospital'" size="small" type="primary" link @click="discharge(row)">
            办理出院
          </el-button>
          <span v-else>-</span>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="modalOpen" title="新增住院登记" width="480px">
      <el-form :model="form" label-position="top">
        <el-form-item label="患者" required>
          <el-select v-model="form.patient_id" filterable placeholder="选择患者" style="width: 100%">
            <el-option v-for="p in patients" :key="p.id" :value="p.id" :label="`${p.display_name || p.username}（#${p.id}）`" />
          </el-select>
        </el-form-item>
        <el-form-item label="科室" required>
          <el-select v-model="form.department" placeholder="选择科室" style="width: 100%">
            <el-option v-for="d in DEPARTMENTS" :key="d" :value="d" :label="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="入院日期" required>
          <el-date-picker v-model="form.admit_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="初步诊断">
          <el-input v-model="form.diagnosis" placeholder="选填" />
        </el-form-item>
        <div style="display: flex; gap: 8px">
          <el-form-item label="病区" style="flex: 1">
            <el-input v-model="form.ward" placeholder="病区" />
          </el-form-item>
          <el-form-item label="床号" style="flex: 1">
            <el-input v-model="form.bed_no" placeholder="床号" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="modalOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">登记</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { doctorApi } from '../api/endpoints'
import type { Hospitalization, PatientSummary } from '../types'

const DEPARTMENTS = [
  '心血管内科', '呼吸内科', '消化内科', '神经内科', '内分泌科',
  '肾内科', '风湿免疫科', '感染科', '骨科', '皮肤科', '儿科', '妇产科', '普外科',
]

const items = ref<Hospitalization[]>([])
const status = ref('')
const loading = ref(false)
const modalOpen = ref(false)
const submitting = ref(false)
const patients = ref<PatientSummary[]>([])
const form = reactive({
  patient_id: undefined as number | undefined,
  department: '',
  admit_date: '' as string,
  diagnosis: '',
  ward: '',
  bed_no: '',
})

async function load() {
  loading.value = true
  try {
    items.value = await doctorApi.hospitalizations({ status: status.value || undefined })
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  doctorApi
    .patients({ page_size: 50 })
    .then((d) => (patients.value = d.items))
    .catch(() => {})
})

function openModal() {
  form.patient_id = undefined
  form.department = ''
  form.admit_date = ''
  form.diagnosis = ''
  form.ward = ''
  form.bed_no = ''
  modalOpen.value = true
}

async function submit() {
  if (!form.patient_id || !form.department || !form.admit_date) {
    ElMessage.warning('请完整填写患者、科室与入院日期')
    return
  }
  submitting.value = true
  try {
    await doctorApi.createHospitalization({
      patient_id: form.patient_id,
      department: form.department,
      admit_date: form.admit_date,
      diagnosis: form.diagnosis,
      ward: form.ward,
      bed_no: form.bed_no,
    })
    ElMessage.success('住院登记成功')
    modalOpen.value = false
    load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    submitting.value = false
  }
}

async function discharge(r: Hospitalization) {
  try {
    await ElMessageBox.confirm(`办理出院（${r.diagnosis || r.department}）？`, '提示', { confirmButtonText: '确认出院' })
    await doctorApi.updateHospitalization(r.id, { status: 'discharged', discharge_date: dayjs().format('YYYY-MM-DD') })
    ElMessage.success('已办理出院')
    load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error((e as Error).message)
  }
}
</script>
