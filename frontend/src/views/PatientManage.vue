<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">患者管理</h2>
      <div class="spacer"></div>
      <el-input
        v-model="searchText"
        placeholder="搜索患者姓名"
        clearable
        :prefix-icon="'Search'"
        style="width: 220px"
      />
    </div>

    <el-row :gutter="16">
      <!-- 患者列表 -->
      <el-col :xs="24" :md="8" :lg="7">
        <el-card shadow="never" class="patient-panel">
          <div class="patient-count">共 {{ filteredPatients.length }} 位患者</div>
          <el-scrollbar class="patient-list">
            <div
              v-for="p in filteredPatients"
              :key="p.id"
              class="patient-item"
              :class="{ active: selectedId === p.id }"
              @click="selectPatient(p)"
            >
              <el-avatar :size="34" class="patient-avatar">
                {{ p.name.slice(0, 1) }}
              </el-avatar>
              <div class="patient-info">
                <div class="patient-name text-ellipsis">{{ p.name }}</div>
                <div class="patient-meta">{{ p.hospCount }} 次住院 · 最近 {{ p.lastDept || '未知' }}</div>
              </div>
              <el-icon v-if="selectedId === p.id" class="check-icon"><Check /></el-icon>
            </div>
            <el-empty v-if="!filteredPatients.length" description="暂无患者数据" :image-size="60" />
          </el-scrollbar>
        </el-card>
      </el-col>

      <!-- 患者详情 -->
      <el-col :xs="24" :md="16" :lg="17">
        <el-card v-if="!selectedPatient" shadow="never" class="detail-empty">
          <el-empty description="选择左侧患者查看详情" />
        </el-card>

        <template v-else>
          <el-card shadow="never" class="detail-card">
            <div class="flex-between">
              <h3 class="card-title">
                <el-icon><User /></el-icon>
                {{ selectedPatient.name }}
                <el-tag size="small" effect="plain">患者ID: {{ selectedPatient.id }}</el-tag>
              </h3>
              <el-button size="small" @click="selectedId = undefined">关闭</el-button>
            </div>

            <el-tabs v-model="detailTab">
              <el-tab-pane label="住院记录" name="hosp">
                <el-table :data="detailHosp" v-loading="detailLoading" stripe size="small">
                  <el-table-column prop="department" label="科室" width="90" />
                  <el-table-column prop="diagnosis" label="诊断" min-width="140" show-overflow-tooltip />
                  <el-table-column prop="admit_date" label="入院" width="100" />
                  <el-table-column prop="discharge_date" label="出院" width="100">
                    <template #default="{ row }">{{ row.discharge_date || '-' }}</template>
                  </el-table-column>
                  <el-table-column prop="doctor_name" label="医生" width="80" />
                  <el-table-column label="状态" width="80">
                    <template #default="{ row }">
                      <el-tag :type="hospStatus(row.status).type" size="small">
                        {{ hospStatus(row.status).label }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>

              <el-tab-pane label="消费明细" name="bills">
                <el-table :data="detailBills" v-loading="billLoading" stripe size="small">
                  <el-table-column prop="bill_no" label="账单号" width="150" />
                  <el-table-column prop="category" label="类别" width="80" />
                  <el-table-column prop="description" label="说明" min-width="140" show-overflow-tooltip />
                  <el-table-column prop="amount" label="金额" width="90" align="right">
                    <template #default="{ row }">¥{{ Number(row.amount || 0).toFixed(2) }}</template>
                  </el-table-column>
                  <el-table-column label="状态" width="80">
                    <template #default="{ row }">
                      <el-tag :type="billStatus(row.status).type" size="small">
                        {{ billStatus(row.status).label }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="created_at" label="时间" width="150">
                    <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>
            </el-tabs>
          </el-card>
        </template>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import {computed, onMounted, ref, watch} from 'vue'
import {medicalApi} from '@/api'
import type {Bill, Hospitalization} from '@/types'
import {useAuthStore} from '@/stores/auth'
import {BILL_STATUS, HOSPITAL_STATUS, pickStatus} from '@/utils/constants'
import {formatDateTime} from '@/utils/format'

const auth = useAuthStore()

interface PatientSummary {
  id: number
  name: string
  hospCount: number
  lastDept?: string
}

const patients = ref<PatientSummary[]>([])
const searchText = ref('')
const selectedId = ref<number | undefined>(undefined)

const detailTab = ref('hosp')
const detailLoading = ref(false)
const billLoading = ref(false)
const detailHosp = ref<Hospitalization[]>([])
const detailBills = ref<Bill[]>([])

const filteredPatients = computed(() => {
  const kw = searchText.value.trim()
  if (!kw) return patients.value
  return patients.value.filter((p) => p.name.includes(kw))
})

const selectedPatient = computed(() =>
  patients.value.find((p) => p.id === selectedId.value),
)

/** 构建患者列表（医生/管理员可见全部住院信息） */
async function loadPatients() {
  try {
    const res = await medicalApi.listHospitalizations({ size: 1000 })
    const map = new Map<number, PatientSummary>()
    for (const h of res.list || []) {
      const id = h.patient_id
      if (!id) continue
      const existing = map.get(id)
      if (existing) {
        existing.hospCount += 1
        existing.lastDept = h.department
      } else {
        map.set(id, {
          id,
          name: h.patient_name || `患者#${id}`,
          hospCount: 1,
          lastDept: h.department,
        })
      }
    }
    patients.value = Array.from(map.values()).sort((a, b) => b.hospCount - a.hospCount)
  } catch {
    patients.value = []
  }
}

async function selectPatient(p: PatientSummary) {
  selectedId.value = p.id
  detailTab.value = 'hosp'
  loadDetail(p.id)
}

async function loadDetail(patientId: number) {
  detailLoading.value = true
  billLoading.value = true
  try {
    const [hosp, bills] = await Promise.all([
      medicalApi.listHospitalizations({ patient_id: patientId, size: 100 }),
      medicalApi.listBills({ patient_id: patientId, size: 100 }),
    ])
    detailHosp.value = hosp.list || []
    detailBills.value = bills.list || []
  } catch {
    detailHosp.value = []
    detailBills.value = []
  } finally {
    detailLoading.value = false
    billLoading.value = false
  }
}

function hospStatus(s?: string) {
  return pickStatus(HOSPITAL_STATUS, s)
}
function billStatus(s?: string) {
  return pickStatus(BILL_STATUS, s)
}
function fmtTime(t?: string) {
  return formatDateTime(t)
}

watch(searchText, () => {
  // 搜索后自动选中第一个匹配患者
  if (filteredPatients.value.length > 0) {
    selectPatient(filteredPatients.value[0])
  }
})

onMounted(() => {
  loadPatients().then(() => {
    if (patients.value.length) selectPatient(patients.value[0])
  })
})
</script>

<style scoped>
.patient-panel {
  height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
  border-radius: 10px;
}

.patient-count {
  font-size: 13px;
  color: #909399;
  margin-bottom: 10px;
}

.patient-list {
  flex: 1;
}

.patient-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 6px;
  transition: background 0.15s;
}

.patient-item:hover {
  background: #f5f7fa;
}

.patient-item.active {
  background: #ecf5ff;
}

.patient-avatar {
  background: #409eff;
  color: #fff;
  flex-shrink: 0;
}

.patient-info {
  flex: 1;
  min-width: 0;
}

.patient-name {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

.patient-meta {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.check-icon {
  color: #409eff;
  flex-shrink: 0;
}

.detail-empty {
  height: calc(100vh - 140px);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
}

.detail-card {
  border-radius: 10px;
}
</style>
