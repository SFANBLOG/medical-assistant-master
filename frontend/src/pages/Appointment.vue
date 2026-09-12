<template>
  <el-card shadow="never">
    <template #header>预约挂号</template>
    <el-form :model="form" inline>
      <el-form-item label="科室"><el-input v-model="form.department" placeholder="如 呼吸内科" /></el-form-item>
      <el-form-item label="日期"><el-date-picker v-model="form.date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
      <el-form-item label="时段">
        <el-select v-model="form.time_slot" style="width:160px">
          <el-option v-for="s in slots" :key="s" :label="s" :value="s" />
        </el-select>
      </el-form-item>
      <el-form-item label="症状"><el-input v-model="form.symptom" placeholder="简要描述" /></el-form-item>
      <el-form-item><el-button type="primary" @click="submit">提交预约</el-button></el-form-item>
    </el-form>

    <el-divider />
    <el-table :data="appts" style="width:100%">
      <el-table-column prop="department" label="科室" />
      <el-table-column prop="date" label="日期" />
      <el-table-column prop="time_slot" label="时段" />
      <el-table-column prop="symptom" label="症状" />
      <el-table-column prop="status" label="状态" />
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const slots = ['08:00-09:00', '09:00-10:00', '10:00-11:00', '14:00-15:00', '15:00-16:00']
const form = ref({ department: '', date: '', time_slot: '', symptom: '' })
const appts = ref([])

async function load() { try { const r = await api.patientAppts(); if (r.ok) appts.value = r.data } catch (e) {} }
onMounted(load)

async function submit() {
  if (!form.value.department || !form.value.date) return ElMessage.warning('请填写科室与日期')
  const r = await api.createAppt(form.value)
  if (r.ok) { ElMessage.success('预约成功'); form.value = { department: '', date: '', time_slot: '', symptom: '' }; load() }
  else ElMessage.error(r.error || '失败')
}
</script>
