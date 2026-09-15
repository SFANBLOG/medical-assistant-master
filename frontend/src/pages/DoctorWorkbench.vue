<template>
  <div>
    <el-card shadow="never" style="margin-bottom:16px">
      <template #header>住院信息管理</template>
      <el-form :model="form" inline>
        <el-form-item label="患者ID"><el-input v-model="form.patient_id" /></el-form-item>
        <el-form-item label="科室"><el-input v-model="form.department" /></el-form-item>
        <el-form-item label="诊断"><el-input v-model="form.diagnosis" /></el-form-item>
        <el-form-item label="入院日期"><el-date-picker v-model="form.admit_date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item><el-button type="primary" @click="add">登记住院</el-button></el-form-item>
      </el-form>
      <el-table :data="hosp" style="width:100%">
        <el-table-column prop="patient_id" label="患者ID" />
        <el-table-column prop="department" label="科室" />
        <el-table-column prop="diagnosis" label="诊断" />
        <el-table-column prop="admit_date" label="入院" />
        <el-table-column prop="status" label="状态" />
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>患者列表</template>
      <el-table :data="patients" style="width:100%">
        <el-table-column prop="id" label="ID" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="display_name" label="姓名" />
        <el-table-column prop="role" label="角色" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'

const hosp = ref([]); const patients = ref([])
const form = ref({ patient_id: '', department: '', diagnosis: '', admit_date: '' })

async function load() {
  try { const r = await api.doctorHosp(); if (r.ok) hosp.value = r.data } catch (e) {}
  try { const r = await api.doctorPatients(); if (r.ok) patients.value = r.data } catch (e) {}
}
onMounted(load)

async function add() {
  if (!form.value.patient_id) return ElMessage.warning('请填写患者ID')
  const r = await api.createHosp(form.value)
  if (r.ok) { ElMessage.success('登记成功'); form.value = { patient_id: '', department: '', diagnosis: '', admit_date: '' }; load() }
  else ElMessage.error(r.error || '失败')
}
</script>
