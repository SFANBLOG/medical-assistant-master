<template>
  <div class="page-container">
    <div class="page-toolbar">
      <h2 class="page-title">健康档案</h2>
      <div class="spacer"></div>
      <template v-if="canViewAll">
        <span class="filter-label">患者</span>
        <el-select
          v-model="patientId"
          placeholder="全部患者"
          clearable
          filterable
          style="width: 180px"
        >
          <el-option
            v-for="p in patientOptions"
            :key="p.id"
            :label="p.name"
            :value="p.id"
          />
        </el-select>
      </template>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- 住院记录 -->
      <el-tab-pane label="住院记录" name="hosp">
        <el-table :data="hospList" v-loading="hospLoading" stripe>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="patient_name" label="患者" min-width="90" />
          <el-table-column prop="department" label="科室" min-width="90" />
          <el-table-column prop="diagnosis" label="诊断" min-width="140" show-overflow-tooltip />
          <el-table-column prop="admit_date" label="入院日期" width="110" />
          <el-table-column prop="discharge_date" label="出院日期" width="110">
            <template #default="{ row }">{{ row.discharge_date || '-' }}</template>
          </el-table-column>
          <el-table-column prop="doctor_name" label="主治医生" min-width="90" />
          <el-table-column prop="total_cost" label="费用" width="90" align="right">
            <template #default="{ row }">¥{{ Number(row.total_cost || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="hospStatus(row.status).type" size="small">
                {{ hospStatus(row.status).label }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          class="pager"
          layout="total, prev, pager, next"
          :total="hospTotal"
          :page-size="hospQuery.size"
          :current-page="hospQuery.page"
          @current-change="(p) => loadHosp(p)"
        />
      </el-tab-pane>

      <!-- 消费明细 -->
      <el-tab-pane label="消费明细" name="bill">
        <el-table :data="billList" v-loading="billLoading" stripe>
          <el-table-column prop="bill_no" label="账单号" width="160" />
          <el-table-column prop="patient_name" label="患者" min-width="90" />
          <el-table-column prop="category" label="类别" width="90">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ row.category }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="说明" min-width="160" show-overflow-tooltip />
          <el-table-column prop="amount" label="金额" width="100" align="right">
            <template #default="{ row }">¥{{ Number(row.amount || 0).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="billStatus(row.status).type" size="small">
                {{ billStatus(row.status).label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="160">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
        <el-pagination
          class="pager"
          layout="total, prev, pager, next"
          :total="billTotal"
          :page-size="billQuery.size"
          :current-page="billQuery.page"
          @current-change="(p) => loadBills(p)"
        />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { medicalApi, getPatientOptions } from '@/api'
import type { Hospitalization, Bill } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { pickStatus, HOSPITAL_STATUS, BILL_STATUS } from '@/utils/constants'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()
const canViewAll = computed(() => ['doctor', 'admin'].includes(auth.role))

const activeTab = ref('hosp')
const patientId = ref<number | undefined>(undefined)
const patientOptions = ref<{ id: number; name: string }[]>([])

/* 住院 */
const hospLoading = ref(false)
const hospList = ref<Hospitalization[]>([])
const hospTotal = ref(0)
const hospQuery = reactive({ page: 1, size: 10 })

/* 账单 */
const billLoading = ref(false)
const billList = ref<Bill[]>([])
const billTotal = ref(0)
const billQuery = reactive({ page: 1, size: 10 })

async function loadHosp(page = 1) {
  hospLoading.value = true
  hospQuery.page = page
  try {
    const params: Record<string, unknown> = {
      page: hospQuery.page,
      size: hospQuery.size,
    }
    if (canViewAll.value && patientId.value) params.patient_id = patientId.value
    const res = await medicalApi.listHospitalizations(params)
    hospList.value = res.list || []
    hospTotal.value = res.total
  } catch (e: unknown) {
    hospList.value = []
    hospTotal.value = 0
    /* 忽略错误提示 */
  } finally {
    hospLoading.value = false
  }
}

async function loadBills(page = 1) {
  billLoading.value = true
  billQuery.page = page
  try {
    const params: Record<string, unknown> = {
      page: billQuery.page,
      size: billQuery.size,
    }
    if (canViewAll.value && patientId.value) params.patient_id = patientId.value
    const res = await medicalApi.listBills(params)
    billList.value = res.list || []
    billTotal.value = res.total
  } catch (e: unknown) {
    billList.value = []
    billTotal.value = 0
  } finally {
    billLoading.value = false
  }
}

watch(patientId, () => {
  if (activeTab.value === 'hosp') loadHosp(1)
  else loadBills(1)
})

watch(activeTab, (tab) => {
  if (tab === 'hosp') loadHosp(1)
  else loadBills(1)
})

function hospStatus(s?: string) {
  return pickStatus(HOSPITAL_STATUS, s)
}
function billStatus(s?: string) {
  return pickStatus(BILL_STATUS, s)
}
function fmtTime(t?: string) {
  return formatDateTime(t)
}

onMounted(async () => {
  if (canViewAll.value) {
    patientOptions.value = await getPatientOptions(auth.role)
  }
  loadHosp(1)
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
