import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/api'

/**
 * 4.1/4.2 产出：求解任务 store + 轮询器
 *
 * 关键设计：
 *  1. 状态机 idle → running → done/failed，转换收敛在 submit / applySnapshot / reset
 *     与轮询错误收尾（连续 3 次拉取失败判 failed，防 mock 重启丢任务后无限转圈）。
 *  2. 轮询器内置于 store：setTimeout 递归（不用 setInterval，响应慢也不会重叠），
 *     约 1s 一跳，done/failed 即止；防重入靠 polling 开关。
 *     组件卸载时视图调 stopPolling()（任务在后端照跑）；回页 onMounted 见
 *     running 再 startPolling() 即可续上——与"切页保活"一致的续轮询路径。
 *  3. 提交参数对齐 mock 契约：POST /api/solve { case, peak, time_limit_s } → { task_id }。
 *  4. done 时 summary/cost_terms/timeseries/solver/params_used 落 store，供结果页直接用；
 *     failed 时保留引擎 messages，错误文案由 4.5 查 describe_errors 表渲染，此处不编文案。
 */

/** 任务状态机：idle → running → done / failed */
export type SolveStatus = 'idle' | 'running' | 'done' | 'failed'

/** 提交 /api/solve 的请求参数（与 mock 契约字段一致） */
export interface SolveParams {
  case: string
  peak: string
  time_limit_s: number
}

export const useSolveStore = defineStore('solve', () => {
  // ---------- 状态机 ----------
  const status = ref<SolveStatus>('idle')
  const taskId = ref('')

  // ---------- 进度快照字段（/api/task/{id}） ----------
  /** 0~1 */
  const progress = ref(0)
  const stage = ref('')
  const logs = ref<string[]>([])

  // ---------- 结果（done 时落 store，供结果页用） ----------
  const summary = ref<Record<string, any> | null>(null)
  const costTerms = ref<Record<string, any> | null>(null)
  const timeseries = ref<Record<string, any> | null>(null)
  const solver = ref<Record<string, any> | null>(null)
  const paramsUsed = ref<Record<string, any> | null>(null)
  /** failed 时引擎返回的 messages（契约：{status:"failed", messages:[...]}） */
  const messages = ref<string[]>([])

  /** 最近一次提交的参数（重跑 / 展示用） */
  const lastParams = ref<SolveParams | null>(null)

  const isRunning = computed(() => status.value === 'running')
  /** 0~100，el-progress 直接用 */
  const progressPct = computed(() => Math.round(progress.value * 100))

  /**
   * 提交 /api/solve 建任务。成功 → running + taskId；网络层失败 → failed。
   * running 中拒绝重复提交（4.3 按钮禁用之外的第二道保险）。
   * 返回是否成功进入 running。
   */
  async function submit(params: SolveParams): Promise<boolean> {
    if (status.value === 'running') return false
    resetResult()
    lastParams.value = { ...params }
    try {
      const res = await api.solve(params)
      const tid = res.data?.task_id
      if (!tid) throw new Error('E_NO_TASK_ID')
      taskId.value = tid
      status.value = 'running'
      progress.value = 0
      stage.value = '排队'
      logs.value = []
      return true
    } catch (e: unknown) {
      status.value = 'failed'
      taskId.value = ''
      messages.value = [e instanceof Error ? e.message : String(e)]
      return false
    }
  }

  /**
   * 应用一次 /api/task/{id} 快照 —— 运行期状态转换的唯一入口。
   * 非本任务 / 非 running 期的快照直接丢弃（防轮询串包）。
   */
  function applySnapshot(d: any) {
    if (!d || status.value !== 'running') return
    if (d.task_id && d.task_id !== taskId.value) return
    progress.value = d.progress ?? progress.value
    stage.value = d.stage ?? stage.value
    if (Array.isArray(d.logs)) logs.value = d.logs
    if (d.status === 'done') {
      status.value = 'done'
      progress.value = 1
      summary.value = d.summary ?? null
      costTerms.value = d.cost_terms ?? null
      timeseries.value = d.timeseries ?? null
      solver.value = d.solver ?? null
      paramsUsed.value = d.params_used ?? null
    } else if (d.status === 'failed') {
      status.value = 'failed'
      messages.value = Array.isArray(d.messages) ? d.messages : []
    }
  }

  // ---------- 4.2 轮询器 ----------
  // 非响应式实现细节：定时器句柄 / 循环开关 / 连续失败计数，不暴露给视图
  let timer: ReturnType<typeof setTimeout> | null = null
  let polling = false
  let failCount = 0
  const POLL_INTERVAL_MS = 1000
  const MAX_POLL_FAILURES = 3

  /**
   * 开始轮询 /api/task/{id}。防重入：已在轮询 / 非 running / 无 taskId 直接返回。
   * 终止条件：done / failed / 连续失败超限 / stopPolling()。
   */
  function startPolling(intervalMs = POLL_INTERVAL_MS) {
    if (polling || status.value !== 'running' || !taskId.value) return
    polling = true
    failCount = 0
    const tick = async () => {
      if (!polling) return
      try {
        const res = await api.task(taskId.value)
        failCount = 0
        applySnapshot(res.data) // done/failed 的状态转换在这里发生
      } catch (e: unknown) {
        // 偶发抖动不杀任务；连续超限才判 failed（如 mock 重启把任务丢了）
        if (++failCount >= MAX_POLL_FAILURES) {
          status.value = 'failed'
          messages.value = [e instanceof Error ? e.message : String(e)]
        }
      }
      if (polling && status.value === 'running') {
        timer = setTimeout(tick, intervalMs)
      } else {
        stopPolling()
      }
    }
    void tick() // 立即第一跳，不等 1s
  }

  /** 停止轮询（组件卸载 / reset / 任务终止时调用；幂等） */
  function stopPolling() {
    polling = false
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  function resetResult() {
    summary.value = null
    costTerms.value = null
    timeseries.value = null
    solver.value = null
    paramsUsed.value = null
    messages.value = []
  }

  /** 回到 idle 并清空任务（开始新一次求解 / 用户主动重置时用）；先停轮询防泄漏 */
  function reset() {
    stopPolling()
    status.value = 'idle'
    taskId.value = ''
    progress.value = 0
    stage.value = ''
    logs.value = []
    resetResult()
  }

  return {
    status,
    taskId,
    progress,
    stage,
    logs,
    summary,
    costTerms,
    timeseries,
    solver,
    paramsUsed,
    messages,
    lastParams,
    isRunning,
    progressPct,
    submit,
    applySnapshot,
    startPolling,
    stopPolling,
    reset,
  }
})
