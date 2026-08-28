<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">护理工作台</h2>
      <div class="spacer"></div>
      <span class="filter-label">患者</span>
      <el-select
        v-model="patientId"
        placeholder="全部患者"
        clearable
        filterable
        style="width: 160px"
      >
        <el-option v-for="p in patientOptions" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" :icon="'Plus'" @click="openCreate">新建护理记录</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="patient_name" label="患者" min-width="90" />
        <el-table-column prop="nurse_name" label="护士" min-width="90" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="nursingType(row.record_type).type" size="small">
              {{ nursingType(row.record_type).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="护理内容" min-width="260" show-overflow-tooltip />
        <el-table-column prop="recorded_at" label="时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.recorded_at) }}</template>
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

    <!-- 新建护理记录 -->
    <el-dialog v-model="dialogVisible" title="新建护理记录" width="520px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="患者" required>
          <el-select v-model="form.patient_id" placeholder="选择患者" filterable style="width: 100%">
            <el-option v-for="p in patientOptions" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="记录类型">
          <el-select v-model="form.record_type" style="width: 100%">
            <el-option label="日常护理" value="daily" />
            <el-option label="用药护理" value="medication" />
            <el-option label="生命体征" value="vitals" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="护理内容" required>
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="4"
            placeholder="填写护理措施、患者状况及观察结果"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { medicalApi, getPatientOptions } from '@/api'
import type { NursingRecord } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { pickStatus, NURSING_TYPES } from '@/utils/constants'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()

const loading = ref(false)
const saving = ref(false)
const list = ref<NursingRecord[]>([])
const total = ref(0)
const query = reactive({ page: 1, size: 10 })
const patientId = ref<number | undefined>(undefined)
const patientOptions = ref<{ id: number; name: string }[]>([])

const dialogVisible = ref(false)
const form = reactive<Partial<NursingRecord>>({
  patient_id: undefined,
  record_type: 'daily',
  content: '',
})

async function load(page = 1) {
  loading.value = true
  query.page = page
  try {
    const params: Record<string, unknown> = { page: query.page, size: query.size }
    if (patientId.value) params.patient_id = patientId.value
    const res = await medicalApi.listNursingRecords(params)
    list.value = res.list || []
    total.value = res.total
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, { patient_id: undefined, record_type: 'daily', content: '' })
  dialogVisible.value = true
}

async function save() {
  if (!form.patient_id) {
    ElMessage.warning('请选择患者')
    return
  }
  if (!form.content?.trim()) {
    ElMessage.warning('请填写护理内容')
    return
  }
  saving.value = true
  try {
    await medicalApi.createNursingRecord({ ...form })
    ElMessage.success('护理记录已保存')
    dialogVisible.value = false
    load(query.page)
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

function nursingType(t?: string) {
  return pickStatus(NURSING_TYPES, t)
}

function fmtTime(t?: string) {
  return formatDateTime(t)
}

watch(patientId, () => load(1))

onMounted(async () => {
  patientOptions.value = await getPatientOptions(auth.role)
  load(1)
})
</script>

<style scoped>
.filter-label {
  font-size: 13px;
  color: #909399;
}

.pager {
  margin-top: 14px;
  justify-content: flex-end;
}
</style>
