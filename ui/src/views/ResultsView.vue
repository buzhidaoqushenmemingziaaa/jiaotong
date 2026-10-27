<script setup lang="ts">
/**
 * 结果总览页 —— 第 5 步（KPI 卡片）
 *
 * 数据来源：useSolveStore。求解完成时 summary/cost_terms/solver/params_used/result_status
 * 落 store，本页不再请求后端，切页/回页读数即可（与求解页的"切页保活"一致）。
 *
 * ★ v2 契约口径（2026-10-17 定稿，与 Mock 后端已对齐）：
 *   - summary 11 字段：objective / cost_wait / cost_crowd1 / cost_crowd2 / cost_km /
 *     cost_hold / total_wakeups / max_standby / structure_changes / peak_online / solve_time_s
 *   - cost_terms 键：wait_raw / crowd1_raw / crowd2_raw / km_raw / hold_raw
 *   - solver 6 字段：name / status / gap / variables / constraints / runtime_s
 *   - result_status：optimal / infeasible / timeout / failed
 *   - validate：[{code, name, pass, detail}]（无 field 字段）
 *
 * KPI 渲染策略：有则显示 —— 以字段是否存在决定是否出卡，不硬编、不臆造。
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { Check, Close } from '@element-plus/icons-vue'
import { useSolveStore } from '@/stores/solve'

const router = useRouter()
const store = useSolveStore()
const { status, resultStatus, summary, costTerms, solver, paramsUsed, validate, lastParams } = storeToRefs(store)

/** 结果显示条件：有 summary 即视为本次求解有结果 */
const hasResult = computed(() => summary.value != null)

/** 求解结果态优先读 v2 的 result_status（optimal/infeasible/timeout/failed），否则回退到生命周期 status */
const resultTag = computed(() => {
  const rs = resultStatus.value || ''
  if (rs === 'optimal') return { type: 'success' as const, text: '最优解' }
  if (rs === 'infeasible') return { type: 'danger' as const, text: '不可行' }
  if (rs === 'timeout') return { type: 'warning' as const, text: '超时' }
  if (rs === 'failed') return { type: 'danger' as const, text: '失败' }
  // 回退：生命周期 status
  if (status.value === 'done') return { type: 'success' as const, text: '求解完成' }
  if (status.value === 'failed') return { type: 'danger' as const, text: '求解失败' }
  if (status.value === 'running') return { type: 'warning' as const, text: '求解中' }
  return { type: 'info' as const, text: '未求解' }
})

/** 数值格式化：非有限数一律显示占位符，绝不显示 NaN/undefined */
function fmt(v: unknown, digits = 2): string {
  return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—'
}

const hasVal = (v: unknown) => v !== undefined && v !== null

interface Kpi {
  key: string
  label: string
  unit: string
  digits: number
  hint?: string
}

/** 主 KPI：mock / 示例数据保证提供（00_先读C.md §3.2 第 6 条点名的三项） */
const coreKpis: Kpi[] = [
  { key: 'objective', label: '目标值', unit: '—', digits: 4, hint: '归一化目标，跨方案可比' },
  { key: 'peak_online', label: '峰值在线车底', unit: '列', digits: 0, hint: '全程峰值在线数' },
  { key: 'solve_time_s', label: '求解耗时', unit: 's', digits: 2 },
]

/** 扩展 KPI：v2 summary 11 字段中有则显示（含新拆出的 crowd1/crowd2） */
const extraKpis: Kpi[] = [
  { key: 'cost_wait', label: '等待成本', unit: '人·h', digits: 1 },
  { key: 'cost_crowd1', label: '超定员缺口', unit: '人/h', digits: 1 },
  { key: 'cost_crowd2', label: '超最大载客缺口', unit: '人/h', digits: 1 },
  { key: 'cost_km', label: '车公里', unit: '列·km', digits: 1 },
  { key: 'cost_hold', label: '待班成本', unit: '列·步', digits: 1 },
  { key: 'total_wakeups', label: '唤醒总数', unit: '列', digits: 0 },
  { key: 'max_standby', label: '最大待班', unit: '列', digits: 0 },
  { key: 'structure_changes', label: '交路调整', unit: '次', digits: 0 },
]

const s = computed<Record<string, any>>(() => summary.value ?? {})
const coreCards = computed(() => coreKpis.map((k) => ({ ...k, value: s.value[k.key] })))
const extraCards = computed(() =>
  extraKpis.filter((k) => hasVal(s.value[k.key])).map((k) => ({ ...k, value: s.value[k.key] })),
)

/**
 * 成本项原始量（cost_terms，v2 定稿键 *_raw）。
 * ★ 各项量纲不同，不可直接比大小；objective 是归一加权和，跨方案才可比。
 */
const costRows = computed(() => {
  const c = costTerms.value ?? {}
  return [
    { label: '等待成本', value: c.wait_raw, unit: '人·h' },
    { label: '超定员缺口', value: c.crowd1_raw, unit: '人/h' },
    { label: '超最大载客缺口', value: c.crowd2_raw, unit: '人/h' },
    { label: '车公里', value: c.km_raw, unit: '列·km' },
    { label: '待班成本', value: c.hold_raw, unit: '列·步' },
  ].filter((r) => hasVal(r.value))
})

/** params_used 按车场展开（tau_steps / u_max_tph），供结果自证可复现 */
const paramRows = computed(() => {
  const p = paramsUsed.value ?? {}
  const tau = (p.tau_steps ?? {}) as Record<string, any>
  const umax = (p.u_max_tph ?? {}) as Record<string, any>
  const dids = Array.from(new Set([...Object.keys(tau), ...Object.keys(umax)]))
  return dids.map((d) => ({ d, tau: tau[d], umax: umax[d] }))
})

const solverRows = computed(() => {
  const sv = solver.value ?? {}
  const rows: { label: string; value: string }[] = []
  if (hasVal(sv.name)) rows.push({ label: '求解器', value: String(sv.name) })
  if (hasVal(sv.status)) rows.push({ label: '求解状态', value: String(sv.status) })
  if (hasVal(sv.variables)) rows.push({ label: '变量数', value: String(sv.variables) })
  if (hasVal(sv.constraints)) rows.push({ label: '约束数', value: String(sv.constraints) })
  if (hasVal(sv.gap)) rows.push({ label: 'Gap', value: fmt(sv.gap, 4) })
  if (hasVal(sv.runtime_s)) rows.push({ label: '求解耗时', value: fmt(sv.runtime_s, 2) + ' s' })
  return rows
})

/** 任务级校验（V1-V8 配置自洽性检查） */
const validateItems = computed(() => {
  const items = validate.value?.items
  return Array.isArray(items) ? items : []
})
const validateSummary = computed(() => {
  const items = validateItems.value
  if (items.length === 0) return null
  const passed = items.filter((i: any) => i.pass).length
  return {
    pass: !!validate.value?.pass,
    total: items.length,
    passed,
    failed: items.length - passed,
  }
})

/** 本次提交参数（来源信息，可复现） */
const source = computed(() => {
  const lp = lastParams.value
  return {
    case: lp?.case ?? '—',
    peak: lp?.peak ?? '—',
    timeLimit: lp?.time_limit_s ?? '—',
  }
})

function goSolve() {
  router.push('/solve')
}
</script>

<template>
  <div class="results-view">
    <!-- 无结果：引导回求解页（直开本页 / 刷新后 store 清空时） -->
    <el-card v-if="!hasResult" shadow="never" class="empty-card">
      <el-empty description="暂无求解结果">
        <el-button type="primary" @click="goSolve">去求解</el-button>
      </el-empty>
    </el-card>

    <template v-else>
      <!-- 来源信息：结果可复现、可追溯 -->
      <el-card shadow="never" class="source-card">
        <div class="source-bar">
          <div class="source-items">
            <span class="source-item">
              <span class="label">算例</span>{{ source.case }}
            </span>
            <span class="source-item">
              <span class="label">高峰时段</span>{{ source.peak }}
            </span>
            <span class="source-item">
              <span class="label">求解时限</span>{{ source.timeLimit }} s
            </span>
            <el-tag :type="resultTag.type" effect="light" round>{{ resultTag.text }}</el-tag>
          </div>
          <el-button @click="goSolve">重新求解</el-button>
        </div>
      </el-card>

      <!-- KPI 卡片：主卡 + 有则显示的扩展卡 -->
      <div class="kpi-grid">
        <div v-for="k in coreCards" :key="k.key" class="kpi-card">
          <div class="kpi-label">{{ k.label }}</div>
          <div class="kpi-value">
            {{ fmt(k.value, k.digits) }}<span class="kpi-unit">{{ k.unit === '—' ? '' : k.unit }}</span>
          </div>
          <div v-if="k.hint" class="kpi-hint">{{ k.hint }}</div>
        </div>
        <div v-for="k in extraCards" :key="k.key" class="kpi-card">
          <div class="kpi-label">{{ k.label }}</div>
          <div class="kpi-value">
            {{ fmt(k.value, k.digits) }}<span class="kpi-unit">{{ k.unit }}</span>
          </div>
        </div>
      </div>

      <el-row :gutter="16">
        <!-- 成本项原始量（量纲不同，不可直接比大小） -->
        <el-col :span="12">
          <el-card shadow="never" class="detail-card">
            <template #header>
              成本项（原始量）<span class="card-note">量纲不同，不可直接比大小</span>
            </template>
            <el-table :data="costRows" size="small" :show-header="false" empty-text="本次结果未提供">
              <el-table-column prop="label" width="140" />
              <el-table-column>
                <template #default="{ row }">
                  <span class="num">{{ fmt(row.value, 1) }}</span>
                  <span class="unit">{{ row.unit }}</span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>

        <!-- 求解器与参数：结果自证 -->
        <el-col :span="12">
          <el-card shadow="never" class="detail-card">
            <template #header>求解器</template>
            <el-descriptions :column="1" size="small" border empty-text="未提供">
              <el-descriptions-item v-for="r in solverRows" :key="r.label" :label="r.label">
                {{ r.value }}
              </el-descriptions-item>
            </el-descriptions>

            <div class="params-title">本次生效参数（params_used）</div>
            <el-table
              :data="paramRows"
              size="small"
              empty-text="本次结果未提供"
            >
              <el-table-column prop="d" label="车场" width="90" />
              <el-table-column label="出库提前期 τ（步）">
                <template #default="{ row }">{{ row.tau ?? '—' }}</template>
              </el-table-column>
              <el-table-column label="出入段能力（列/h）">
                <template #default="{ row }">{{ row.umax ?? '—' }}</template>
              </el-table-column>
            </el-table>

            <!-- 任务级校验（V1-V8 配置自洽性） -->
            <template v-if="validateSummary">
              <div class="params-title">
                配置校验
                <span :class="['validate-badge', validateSummary.pass ? 'ok' : 'fail']">
                  {{ validateSummary.pass ? `${validateSummary.passed}/${validateSummary.total} 全部通过` : `${validateSummary.failed} 项未通过` }}
                </span>
              </div>
              <el-collapse class="validate-collapse">
                <el-collapse-item name="v">
                  <template #title>查看 {{ validateSummary.total }} 项校验详情</template>
                  <el-table :data="validateItems" size="small" border>
                    <el-table-column label="状态" width="80" align="center">
                      <template #default="{ row }">
                        <el-icon :color="row.pass ? '#22c55e' : '#ef4444'">
                          <Check v-if="row.pass" /><Close v-else />
                        </el-icon>
                      </template>
                    </el-table-column>
                    <el-table-column prop="code" label="码" width="70" />
                    <el-table-column prop="name" label="检查项" min-width="180" />
                    <el-table-column prop="detail" label="详情" min-width="120">
                      <template #default="{ row }">{{ row.detail || '—' }}</template>
                    </el-table-column>
                  </el-table>
                </el-collapse-item>
              </el-collapse>
            </template>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<style scoped>
.results-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.empty-card {
  min-height: 40vh;
}
.source-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.source-items {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 20px;
}
.source-item {
  font-size: 14px;
  color: var(--el-text-color-primary);
}
.source-item .label {
  margin-right: 8px;
  color: var(--el-text-color-secondary);
}
/* KPI 卡片：自适应网格，不依赖断点（MVP 不做响应式） */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.kpi-card {
  background: #fff;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 18px 20px;
}
.kpi-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.kpi-value {
  margin-top: 8px;
  font-size: 28px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--el-color-primary);
  font-variant-numeric: tabular-nums;
}
.kpi-unit {
  margin-left: 6px;
  font-size: 13px;
  font-weight: normal;
  color: var(--el-text-color-secondary);
}
.kpi-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
.card-note {
  margin-left: 8px;
  font-size: 12px;
  font-weight: normal;
  color: var(--el-text-color-secondary);
}
.num {
  font-variant-numeric: tabular-nums;
}
.unit {
  margin-left: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.params-title {
  margin: 16px 0 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.validate-badge {
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: normal;
}
.validate-badge.ok {
  background: #f0fdf4;
  color: #16a34a;
}
.validate-badge.fail {
  background: #fef2f2;
  color: #dc2626;
}
.validate-collapse {
  margin-top: 8px;
  border: none;
}
.validate-collapse :deep(.el-collapse-item__header) {
  padding-left: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
