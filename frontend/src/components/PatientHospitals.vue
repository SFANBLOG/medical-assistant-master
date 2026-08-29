<template>
  <el-table :data="rows" v-loading="loading" size="small" row-key="id">
    <el-table-column label="入院日期" prop="admit_date" width="120" />
    <el-table-column label="出院日期" width="120">
      <template #default="{ row }">{{ row.discharge_date || '-' }}</template>
    </el-table-column>
    <el-table-column label="科室" prop="department" width="110" />
    <el-table-column label="诊断" prop="diagnosis" min-width="140" show-overflow-tooltip />
    <el-table-column label="主治医生" width="110">
      <template #default="{ row }">{{ row.doctor_name || '-' }}</template>
    </el-table-column>
    <el-table-column label="费用(元)" width="100" align="right">
      <template #default="{ row }">{{ Number(row.total_cost).toLocaleString('zh-CN') }}</template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import {onMounted, ref} from 'vue'
import {ElMessage} from 'element-plus'
import {doctorApi} from '../api/endpoints'
import type {Hospitalization} from '../types'

const props = defineProps<{ patientId: number }>()

const rows = ref<Hospitalization[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    rows.value = await doctorApi.patientHospitalizations(props.patientId)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
})
</script>
