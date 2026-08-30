<template>
  <el-card>
    <template #header>我的健康档案</template>
    <el-alert type="info" :closable="false" style="margin-bottom: 16px"
      title="患者可查询本人的最近住院信息、消费明细与预约挂号记录。" />
    <el-tabs v-model="tab">
      <el-tab-pane label="住院信息" name="hosp">
        <el-table :data="hosp" v-loading="loading" size="small" row-key="id">
          <el-table-column label="入院日期" prop="admit_date" width="120" />
          <el-table-column label="出院日期" width="120">
            <template #default="{ row }">{{ row.discharge_date || '-' }}</template>
          </el-table-column>
          <el-table-column label="科室" prop="department" width="110" />
          <el-table-column label="病床" width="110">
            <template #default="{ row }">{{ [row.ward, row.bed_no].filter(Boolean).join(' ') || '-' }}</template>
          </el-table-column>
          <el-table-column label="诊断" prop="diagnosis" min-width="140" show-overflow-tooltip />
          <el-table-column label="主治医生" width="100">
            <template #default="{ row }">{{ row.doctor_name || '-' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'in_hospital'" type="primary">在院</el-tag>
              <el-tag v-else type="info">已出院</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="住院费用(元)" width="120" align="right">
            <template #default="{ row }">{{ Number(row.total_cost).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="消费明细" name="bills">
        <el-table :data="bills" v-loading="loading" size="small" row-key="id">
          <el-table-column label="账单号" prop="bill_no" width="170" />
          <el-table-column label="类别" prop="category" width="90" />
          <el-table-column label="说明" prop="description" min-width="140" show-overflow-tooltip />
          <el-table-column label="金额(元)" width="120" align="right">
            <template #default="{ row }">{{ Number(row.amount).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'paid'" type="success">已结算</el-tag>
              <el-tag v-else type="warning">未结算</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="日期" prop="created_at" width="120" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="预约挂号" name="appts">
        <el-table :data="appts" v-loading="loading" size="small" row-key="id">
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
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup lang="ts">
import {onMounted, ref} from 'vue'
import {ElMessage} from 'element-plus'
import {patientApi} from '@/api/endpoints'
import type {Appointment, Bill, Hospitalization} from '@/types'
import {APPOINTMENT_STATUS_LABELS} from '@/types'

const APPT_STATUS_LABELS = APPOINTMENT_STATUS_LABELS

const tab = ref('hosp')
const hosp = ref<Hospitalization[]>([])
const bills = ref<Bill[]>([])
const appts = ref<Appointment[]>([])
const loading = ref(true)

onMounted(() => {
  Promise.all([patientApi.hospitalizations(), patientApi.bills(), patientApi.appointments()])
    .then(([h, b, a]) => {
      hosp.value = h
      bills.value = b
      appts.value = a
    })
    .catch((e) => ElMessage.error((e as Error).message))
    .finally(() => (loading.value = false))
})
</script>
