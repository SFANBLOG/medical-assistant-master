<template>
  <el-card>
    <template #header>护理工作台</template>
    <el-tabs v-model="tab">
      <el-tab-pane :label="`患者信息 (${patients.length})`" name="patients">
        <el-table :data="patients" v-loading="loading" size="small" row-key="id">
          <el-table-column label="ID" prop="id" width="60" />
          <el-table-column label="姓名" width="120">
            <template #default="{ row }">{{ row.display_name || '-' }}</template>
          </el-table-column>
          <el-table-column label="用户名" prop="username" width="130" />
          <el-table-column label="当前状态" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.current_status" type="primary">在院</el-tag>
              <el-tag v-else type="info">非住院</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="科室" width="110">
            <template #default="{ row }">{{ row.current_department || '-' }}</template>
          </el-table-column>
          <el-table-column label="床位" width="80">
            <template #default="{ row }">{{ row.current_bed || '-' }}</template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="`护理记录 (${records.length})`" name="records">
        <el-button type="primary" style="margin-bottom: 16px" @click="openModal">
          <el-icon><Plus /></el-icon>&nbsp;新增护理记录
        </el-button>
        <el-table :data="records" v-loading="loading" size="small" row-key="id">
          <el-table-column label="患者" prop="patient_name" width="110" />
          <el-table-column label="类型" width="90">
            <template #default="{ row }"><el-tag>{{ RECORD_TYPE_LABELS[row.record_type] ?? row.record_type }}</el-tag></template>
          </el-table-column>
          <el-table-column label="记录内容" prop="content" min-width="220" show-overflow-tooltip />
          <el-table-column label="记录护士" width="110">
            <template #default="{ row }">{{ row.nurse_name || '-' }}</template>
          </el-table-column>
          <el-table-column label="时间" prop="recorded_at" width="130" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="`我的排班 (${schedules.length})`" name="schedule">
        <el-table :data="schedules" v-loading="loading" size="small" row-key="id">
          <el-table-column label="日期" prop="work_date" width="120" />
          <el-table-column label="班次" width="80">
            <template #default="{ row }"><el-tag>{{ SHIFT_LABELS[row.shift] ?? row.shift }}</el-tag></template>
          </el-table-column>
          <el-table-column label="科室" width="120">
            <template #default="{ row }">{{ row.department || '-' }}</template>
          </el-table-column>
          <el-table-column label="备注" prop="remark" min-width="120" show-overflow-tooltip />
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="modalOpen" title="新增护理记录" width="460px">
      <el-form :model="form" label-position="top">
        <el-form-item label="患者" required>
          <el-select v-model="form.patient_id" filterable placeholder="选择患者" style="width: 100%">
            <el-option v-for="p in patients" :key="p.id" :value="p.id" :label="`${p.display_name || p.username}（#${p.id}）`" />
          </el-select>
        </el-form-item>
        <el-form-item label="记录类型">
          <el-select v-model="form.record_type" style="width: 100%">
            <el-option v-for="(label, value) in RECORD_TYPE_LABELS" :key="value" :value="value" :label="label" />
          </el-select>
        </el-form-item>
        <el-form-item label="记录内容" required>
          <el-input v-model="form.content" type="textarea" :rows="3" placeholder="如：生命体征平稳，遵医嘱给药并观察反应" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modalOpen = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { nurseApi, scheduleApi } from '../api/endpoints'
import { useAuth } from '../stores/auth'
import { SHIFT_LABELS } from '../types'
import type { NursingRecord, PatientSummary, Schedule } from '../types'

const RECORD_TYPE_LABELS: Record<string, string> = {
  daily: '日常护理',
  medication: '给药护理',
  vitals: '生命体征',
  other: '其他',
}

const auth = useAuth()
const tab = ref('patients')
const patients = ref<PatientSummary[]>([])
const records = ref<NursingRecord[]>([])
const schedules = ref<Schedule[]>([])
const loading = ref(false)
const modalOpen = ref(false)
const form = reactive({
  patient_id: undefined as number | undefined,
  record_type: 'daily',
  content: '',
})

async function load() {
  loading.value = true
  try {
    const [p, r, s] = await Promise.all([
      nurseApi.patients(),
      nurseApi.nursingRecords(),
      scheduleApi.list({ staff_id: auth.user?.id }),
    ])
    patients.value = p
    records.value = r
    schedules.value = s
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(load)

function openModal() {
  form.patient_id = undefined
  form.record_type = 'daily'
  form.content = ''
  modalOpen.value = true
}

async function submit() {
  if (!form.patient_id || !form.content.trim()) {
    ElMessage.warning('请选择患者并填写记录内容')
    return
  }
  try {
    await nurseApi.createNursingRecord({
      patient_id: form.patient_id,
      content: form.content,
      record_type: form.record_type,
    })
    ElMessage.success('护理记录已保存')
    modalOpen.value = false
    load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}
</script>
