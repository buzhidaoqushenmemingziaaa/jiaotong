<script setup lang="ts">
/**
 * 方案求解页 —— 4.3 提交区表单
 *
 * 表单三要素 + 运行按钮：
 *  - 算例下拉：/api/cases 拉取（id 作 value）；选中后把 peak 单选同步为该算例
 *    的高峰时段，防 line14_evening 配 morning 的错配（仍可手改）。
 *  - peak 单选：契约值只有 morning / evening（01_数据契约/结果schema说明.md §15）。
 *  - time_limit：秒，el-input-number。
 * 提交 → store.submit() 成功 → store.startPolling()（4.2 轮询器）。
 *
 * 生命周期约定（4.2 定）：卸载 stopPolling()（后端任务照跑）；
 * 回页见 running 重新 startPolling() 续上——切页不丢任务。
 *
 * 4.4 运行进度卡：status 非 idle 即显示。el-progress 用 store.progressPct，
 * running 时 striped-flow 动效，done→success、failed→exception；
 * 日志区等宽字体，watch logs 长度变化后 nextTick 滚到底。
 *
 * 4.5 收尾卡：
 *  - done：摘要卡只直出 summary.objective / solve_time_s 两个无歧义字段 + 跳结果总览
 *    （完整 KPI 卡是第 5 步的事）；summary/timeseries 已在 4.1 落 store 供结果页用。
 *  - failed：messages 逐条经 describe_errors 查表渲染（复用 config store 的
 *    errorText，3.6），查不到原样显示，绝不自编文案。
 *    ★盲区：mock 不会产出 failed，引擎错误码（E_INFEASIBLE 等）查表分支在
 *    当前 mock 下不可达，留待联调回归；网络失败路径用"杀 mock"实测。
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { api } from '@/api'
import { useConfigStore } from '@/stores/config'
import { useSolveStore } from '@/stores/solve'

const router = useRouter()
const store = useSolveStore()
const configStore = useConfigStore()
const { isRunning, taskId, status, stage, logs, progressPct, summary, messages } =
  storeToRefs(store)

/** el-progress 的状态映射：done→success、failed→exception、其余走默认色 */
const progressStatus = computed(() => {
  if (status.value === 'done') return 'success' as const
  if (status.value === 'failed') return 'exception' as const
  return undefined
})

/** 日志容器：新日志到达后自动滚到底（nextTick 等 DOM 先更新） */
const logBox = ref<HTMLElement>()
watch(
  () => logs.value.length,
  async () => {
    await nextTick()
    const el = logBox.value
    if (el) el.scrollTop = el.scrollHeight
  },
)

/** 算例下拉选项（/api/cases 返回 {cases:[...]}） */
interface CaseOption {
  id: string
  case_id?: string
  peak?: string
  steps?: number
  objective?: number
}
const cases = ref<CaseOption[]>([])
const loadingCases = ref(false)
const casesError = ref('')

// ---------- 表单 ----------
const caseId = ref('')
const peak = ref<'morning' | 'evening'>('morning')
const timeLimit = ref(60)
const submitting = ref(false)

async function loadCases() {
  if (loadingCases.value) return
  loadingCases.value = true
  casesError.value = ''
  try {
    const res = await api.cases()
    cases.value = (res.data?.cases ?? []) as CaseOption[]
    // 首次加载默认选第一个算例（并同步 peak）
    if (!caseId.value && cases.value.length > 0) onCaseChange(cases.value[0].id)
  } catch (e: unknown) {
    casesError.value = e instanceof Error ? e.message : '算例列表拉取失败'
  } finally {
    loadingCases.value = false
  }
}

/** 选算例时同步 peak 单选为该算例的高峰时段 */
function onCaseChange(id: string) {
  caseId.value = id
  const c = cases.value.find((x) => x.id === id)
  if (c?.peak === 'morning' || c?.peak === 'evening') peak.value = c.peak
}

async function onRun() {
  if (!caseId.value || isRunning.value || submitting.value) return
  submitting.value = true
  try {
    const ok = await store.submit({
      case: caseId.value,
      peak: peak.value,
      time_limit_s: timeLimit.value,
    })
    if (ok) store.startPolling()
    // 失败路径：store 已转 failed，错误渲染归 4.5
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadCases()
  configStore.loadErrors() // 4.5：failed 时错误码查 describe_errors 表用
  // 回页续轮询：任务在后端仍在跑，store 里状态还是 running
  if (isRunning.value) store.startPolling()
})

/** 4.5：回到 idle 重新发起（清掉摘要/失败卡与旧进度） */
function onReset() {
  store.reset()
}

onUnmounted(() => {
  store.stopPolling()
})
</script>

<template>
  <div class="solve-view">
    <el-card shadow="never" class="submit-card">
      <template #header>提交求解</template>

      <el-alert
        v-if="casesError"
        type="error"
        :closable="false"
        show-icon
        :title="casesError"
      />

      <el-form label-width="96px" @submit.prevent>
        <el-form-item label="算例">
          <el-select
            v-model="caseId"
            placeholder="选择算例"
            :loading="loadingCases"
            :disabled="isRunning"
            class="case-select"
            @change="onCaseChange"
          >
            <el-option
              v-for="c in cases"
              :key="c.id"
              :value="c.id"
              :label="`${c.id}（${c.peak ?? '?'} · 目标 ${c.objective ?? '?'}）`"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="高峰时段">
          <el-radio-group v-model="peak" :disabled="isRunning">
            <el-radio value="morning">早高峰（morning）</el-radio>
            <el-radio value="evening">晚高峰（evening）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="求解时限">
          <el-input-number
            v-model="timeLimit"
            :min="1"
            :max="3600"
            :step="10"
            :disabled="isRunning"
          />
          <span class="unit">秒</span>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :disabled="!caseId || isRunning"
            :loading="submitting"
            @click="onRun"
          >
            {{ isRunning ? '求解中…' : '运行求解' }}
          </el-button>
          <span v-if="isRunning" class="task-hint">
            任务 {{ taskId }} 运行中，可切页，回来后自动续上进度
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 4.4 运行进度卡：任务建立（非 idle）后出现 -->
    <el-card v-if="status !== 'idle'" shadow="never" class="progress-card">
      <template #header>
        <div class="progress-header">
          <span>运行进度</span>
          <span class="stage-text">当前阶段：{{ stage || '—' }}</span>
        </div>
      </template>

      <el-progress
        :percentage="progressPct"
        :status="progressStatus"
        :striped="isRunning"
        :striped-flow="isRunning"
        :stroke-width="16"
      />

      <div ref="logBox" class="log-box">
        <div v-for="(line, i) in logs" :key="i" class="log-line">{{ line }}</div>
        <div v-if="logs.length === 0" class="log-empty">（等待任务日志…）</div>
      </div>
    </el-card>

    <!-- 4.5 done 摘要卡：只直出两个无歧义字段，完整 KPI 归结果总览（第 5 步） -->
    <el-card v-if="status === 'done' && summary" shadow="never" class="result-card">
      <template #header>求解摘要</template>
      <el-alert
        type="success"
        :closable="false"
        show-icon
        :title="`目标值 ${summary.objective ?? '—'} · 求解耗时 ${summary.solve_time_s ?? '—'} s`"
        description="结果（summary/timeseries）已就绪，完整指标与图表见结果总览"
      />
      <div class="result-actions">
        <el-button type="primary" @click="router.push('/results')">查看结果总览</el-button>
        <el-button @click="onReset">重新求解</el-button>
      </div>
    </el-card>

    <!-- 4.5 failed 卡：错误码经 describe_errors 查表，不自编文案 -->
    <el-card v-if="status === 'failed'" shadow="never" class="fail-card">
      <template #header>求解失败</template>
      <el-alert type="error" :closable="false" show-icon title="求解失败">
        <ul class="fail-list">
          <li v-for="(m, i) in messages" :key="i">{{ configStore.errorText(m) }}</li>
        </ul>
      </el-alert>
      <div class="result-actions">
        <el-button @click="onReset">重新求解</el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.solve-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.submit-card {
  max-width: 720px;
}
.progress-card {
  max-width: 720px;
}
.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.stage-text {
  font-size: 13px;
  font-weight: normal;
  color: var(--el-text-color-secondary);
}
/* 日志区：等宽字体 + 固定高度滚动，新日志由 watch 自动滚底 */
.log-box {
  margin-top: 14px;
  height: 220px;
  overflow-y: auto;
  padding: 8px 12px;
  border-radius: 4px;
  background: #111827;
  color: #d1d5db;
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.7;
}
.log-line {
  white-space: pre-wrap;
  word-break: break-all;
}
.log-empty {
  color: #6b7280;
}
.result-card,
.fail-card {
  max-width: 720px;
}
.result-actions {
  margin-top: 12px;
}
.fail-list {
  margin: 4px 0 0;
  padding-left: 18px;
}
.case-select {
  width: 380px;
}
.unit {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
}
.task-hint {
  margin-left: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
