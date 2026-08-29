<template>
  <el-card>
    <template #header>预约挂号</template>
    <el-card shadow="never" style="margin-bottom: 16px">
      <template #header>在线挂号</template>
      <el-form :model="form" label-position="top">
        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="就诊科室" required>
              <el-select v-model="form.department" placeholder="选择科室" style="width: 100%">
                <el-option v-for="d in DEPARTMENTS" :key="d" :value="d" :label="d" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="选择医生（选填）">
              <el-select v-model="form.doctor_id" clearable placeholder="不选由科室随机排号" style="width: 100%">
                <el-option v-for="d in doctors" :key="d.id" :value="d.id" :label="d.display_name || d.username" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="就诊日期" required>
              <el-date-picker v-model="form.date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期"
                :disabled-date="disabledDate" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="就诊时段" required>
              <el-select v-model="form.time_slot" placeholder="选择时段" style="width: 100%">
                <el-option v-for="s in SLOTS" :key="s" :value="s" :label="s" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="16">
            <el-form-item label="主诉/症状（选填）">
              <el-input v-model="form.symptom" placeholder="简单描述症状，便于医生提前了解" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-button type="primary" :loading="submitting" @click="submit">提交预约</el-button>
      </el-form>
    </el-card>

    <el-table :data="items" v-loading="loading" size="small" row-key="id">
      <el-table-column label="科室" prop="department" width="110" />
      <el-table-column label="日期" prop="date" width="120" />
      <el-table-column label="时段" prop="time_slot" width="110" />
      <el-table-column label="医生" width="100">
        <template #default="{ row }">{{ row.doctor_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="主诉" prop="symptom" min-width="120" show-overflow-tooltip />
      <el-table-column label="挂号费(元)" prop="fee" width="110" align="right" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">{{ APPT_STATUS_LABELS[row.status] ?? row.status }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button v-if="row.status !== 'cancelled' && row.status !== 'visited'" size="small" type="danger" link
            @click="cancel(row.id)">取消</el-button>
          <span v-else>-</span>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import {onMounted, reactive, ref} from 'vue'
import {ElMessage} from 'element-plus'
import dayjs from 'dayjs'
import {patientApi} from '../api/endpoints'
import type {Appointment} from '../types'
import {APPOINTMENT_STATUS_LABELS} from '../types'

const APPT_STATUS_LABELS = APPOINTMENT_STATUS_LABELS

const DEPARTMENTS = [
  '心血管内科', '呼吸内科', '消化内科', '神经内科', '内分泌科',
  '肾内科', '风湿免疫科', '感染科', '骨科', '皮肤科', '儿科', '妇产科', '普外科',
]
const SLOTS = ['08:00-08:30', '08:30-09:00', '09:00-09:30', '14:00-14:30', '14:30-15:00']

const items = ref<Appointment[]>([])
const doctors = ref<{ id: number; username: string; display_name: string }[]>([])
const loading = ref(false)
const submitting = ref(false)
const form = reactive({
  department: '',
  date: '' as string,
  time_slot: '',
  doctor_id: undefined as number | undefined,
  symptom: '',
})

function disabledDate(date: Date) {
  return dayjs(date).isBefore(dayjs(), 'day')
}

async function load() {
  loading.value = true
  try {
    const [a, d] = await Promise.all([patientApi.appointments(), patientApi.doctors()])
    items.value = a
    doctors.value = d
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function submit() {
  if (!form.department || !form.date || !form.time_slot) {
    ElMessage.warning('请完整填写科室、日期与时段')
    return
  }
  submitting.value = true
  try {
    await patientApi.createAppointment({
      department: form.department,
      date: form.date,
      time_slot: form.time_slot,
      doctor_id: form.doctor_id,
      symptom: form.symptom,
    })
    ElMessage.success('预约成功')
    form.department = ''
    form.date = ''
    form.time_slot = ''
    form.doctor_id = undefined
    form.symptom = ''
    load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    submitting.value = false
  }
}

async function cancel(id: number) {
  try {
    await patientApi.cancelAppointment(id)
    ElMessage.success('已取消预约')
    load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}
</script>
