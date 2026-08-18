<template>
  <el-card>
    <template #header>
      <div style="display: flex; align-items: center; justify-content: space-between">
        <span>排班管理</span>
        <el-button type="primary" @click="modalOpen = true"><el-icon><Plus /></el-icon>&nbsp;新增排班</el-button>
      </div>
    </template>

    <el-table :data="items" v-loading="loading" size="small" row-key="id">
      <el-table-column label="值班人员" prop="staff_name" width="130" />
      <el-table-column label="身份" width="90">
        <template #default="{ row }"><el-tag>{{ ROLE_LABELS[row.staff_role] ?? row.staff_role }}</el-tag></template>
      </el-table-column>
      <el-table-column label="日期" prop="work_date" width="120" />
      <el-table-column label="班次" width="90">
        <template #default="{ row }">
          <el-tag :type="SHIFT_COLORS[row.shift]">{{ SHIFT_LABELS[row.shift] ?? row.shift }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="科室" width="130">
        <template #default="{ row }">{{ row.department || '-' }}</template>
      </el-table-column>
      <el-table-column label="备注" prop="remark" min-width="120" show-overflow-tooltip />
    </el-table>

    <el-dialog v-model="modalOpen" title="新增排班" width="460px">
      <el-form :model="form" label-position="top">
        <el-form-item label="值班人员" required>
          <el-select v-model="form.staff_id" filterable placeholder="选择医生/护士" style="width: 100%">
            <el-option v-for="s in staffOptions" :key="s.value" :value="s.value" :label="s.label" />
          </el-select>
        </el-form-item>
        <el-form-item label="值班日期" required>
          <el-date-picker v-model="form.work_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
        <el-form-item label="班次" required>
          <el-select v-model="form.shift" style="width: 100%">
            <el-option v-for="(label, value) in SHIFT_LABELS" :key="value" :value="value" :label="label" />
          </el-select>
        </el-form-item>
        <el-form-item label="科室">
          <el-select v-model="form.department" clearable placeholder="选填" style="width: 100%">
            <el-option v-for="d in DEPARTMENTS" :key="d" :value="d" :label="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" placeholder="选填" />
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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { scheduleApi } from '../api/endpoints'
import { ROLE_LABELS, SHIFT_LABELS } from '../types'
import type { Schedule } from '../types'

const SHIFT_COLORS: Record<string, string> = { day: 'primary', night: 'warning', evening: 'danger', off: 'info' }
const DEPARTMENTS = ['心血管内科', '呼吸内科', '消化内科', '神经内科', '内分泌科', '儿科', '急诊科', '骨科']

const items = ref<Schedule[]>([])
const loading = ref(false)
const modalOpen = ref(false)
const form = reactive({
  staff_id: undefined as number | undefined,
  work_date: '' as string,
  shift: 'day',
  department: '',
  remark: '',
})

const staffOptions = computed(() => {
  const seen = new Set<number>()
  return items.value
    .map((s) => ({ value: s.staff_id, label: `${s.staff_name}（${ROLE_LABELS[s.staff_role ?? 'doctor']}）` }))
    .filter((o) => (seen.has(o.value) ? false : (seen.add(o.value), true)))
})

async function load() {
  loading.value = true
  try {
    items.value = await scheduleApi.list()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function submit() {
  if (!form.staff_id || !form.work_date) {
    ElMessage.warning('请选择值班人员与日期')
    return
  }
  try {
    await scheduleApi.create({
      staff_id: form.staff_id,
      work_date: form.work_date,
      shift: form.shift,
      department: form.department,
      remark: form.remark,
    })
    ElMessage.success('排班已保存')
    modalOpen.value = false
    load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}
</script>
