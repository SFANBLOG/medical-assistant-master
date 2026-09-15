<template>
  <div>
    <el-card shadow="never" style="margin-bottom:16px">
      <template #header>护理记录</template>
      <el-form :model="form" inline>
        <el-form-item label="患者ID"><el-input v-model="form.patient_id" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.record_type" style="width:140px">
            <el-option label="日常" value="daily" />
            <el-option label="用药" value="medication" />
            <el-option label="生命体征" value="vitals" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容"><el-input v-model="form.content" style="width:320px" /></el-form-item>
        <el-form-item><el-button type="primary" @click="add">记录</el-button></el-form-item>
      </el-form>
      <el-table :data="records" style="width:100%">
        <el-table-column prop="patient_id" label="患者ID" />
        <el-table-column prop="record_type" label="类型" />
        <el-table-column prop="content" label="内容" />
        <el-table-column prop="recorded_at" label="时间" />
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>排班信息</template>
      <el-table :data="schedules" style="width:100%">
        <el-table-column prop="staff_id" label="员工ID" />
        <el-table-column prop="work_date" label="日期" />
        <el-table-column prop="shift" label="班次" />
        <el-table-column prop="department" label="科室" />
        <el-table-column prop="status" label="状态" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const records = ref([]); const schedules = ref([])
const form = ref({ patient_id: '', record_type: 'daily', content: '' })

async function load() {
  try { const r = await api.nurseRecords(); if (r.ok) records.value = r.data } catch (e) {}
  try { const r = await api.scheduleList(); if (r.ok) schedules.value = r.data } catch (e) {}
}
onMounted(load)

async function add() {
  if (!form.value.patient_id || !form.value.content) return ElMessage.warning('请填写患者ID与内容')
  const r = await api.createNurseRecord(form.value)
  if (r.ok) { ElMessage.success('记录成功'); form.value = { patient_id: '', record_type: 'daily', content: '' }; load() }
  else ElMessage.error(r.error || '失败')
}
</script>
