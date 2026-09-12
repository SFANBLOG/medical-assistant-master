<template>
  <el-card shadow="never">
    <template #header>健康档案（仅本人可见）</template>
    <el-tabs v-model="tab">
      <el-tab-pane label="住院信息" name="hosp">
        <el-table :data="hosp" style="width:100%">
          <el-table-column prop="department" label="科室" />
          <el-table-column prop="admit_date" label="入院日期" />
          <el-table-column prop="diagnosis" label="诊断" />
          <el-table-column prop="status" label="状态" />
          <el-table-column prop="total_cost" label="费用" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="消费明细" name="bill">
        <el-table :data="bills" style="width:100%">
          <el-table-column prop="category" label="类别" />
          <el-table-column prop="description" label="说明" />
          <el-table-column prop="amount" label="金额" />
          <el-table-column prop="status" label="状态" />
        </el-table>
      </el-tab-pane>
      <el-tab-pane label="预约挂号" name="appt">
        <el-table :data="appts" style="width:100%">
          <el-table-column prop="department" label="科室" />
          <el-table-column prop="date" label="日期" />
          <el-table-column prop="time_slot" label="时段" />
          <el-table-column prop="status" label="状态" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const tab = ref('hosp')
const hosp = ref([]); const bills = ref([]); const appts = ref([])

onMounted(async () => {
  try { const r = await api.patientHosp(); if (r.ok) hosp.value = r.data } catch (e) {}
  try { const r = await api.patientBills(); if (r.ok) bills.value = r.data } catch (e) {}
  try { const r = await api.patientAppts(); if (r.ok) appts.value = r.data } catch (e) {}
})
</script>
