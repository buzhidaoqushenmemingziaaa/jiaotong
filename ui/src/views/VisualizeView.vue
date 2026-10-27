<script setup lang="ts">
/**
 * 运行可视化 —— 第 6 步（列车动画 + 时空图 + 客流 vs 运力 + 满载率）
 *
 * ★ 架构：四个 Tab 容器，动态渲染，避免单组件过大
 * ★ 数据策略：聚合精确 + 位置近似（见 AnimCanvas.vue 注释）
 * ★ 验收硬标准：动画在线车底数与 timeseries.a_total 一致（memory.md §11）
 */
import { computed, ref, watch, nextTick, shallowRef, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import * as echarts from 'echarts/core'
import { LineChart, BarChart, HeatmapChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  VisualMapComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsCoreOption } from 'echarts/core'
import { VideoPlay, VideoPause, RefreshLeft } from '@element-plus/icons-vue'
import { useSolveStore } from '@/stores/solve'
import { useConfigStore } from '@/stores/config'
import AnimCanvas from '@/components/visualize/AnimCanvas.vue'

echarts.use([
  LineChart,
  BarChart,
  HeatmapChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  VisualMapComponent,
  DataZoomComponent,
  CanvasRenderer,
])

/** 三个 Mock 算例的拓扑硬编码（前端兜底，联调时 config store 会有真实值） */
const TOPOLOGY_HINTS: Record<string, { stations: string[]; sectionLenKm: number[] }> = {
  toyline_morning: {
    stations: ['A', 'B', 'C', 'D', 'E', 'F'],
    sectionLenKm: [3.0, 4.0, 3.0, 5.0, 2.0], // 17km 合计
  },
  line14_morning: {
    // 深圳 14 号线真实站名（简化）
    stations: ['沙田', '坑梓', '坪山围', '锦龙', '新和', '云山西路', '同乐', '红岭北', '笋岗', '红岭', '市民中心', '岗厦北', '皇岗村', '福田', '石厦', '上沙', '沙尾', '福保'],
    sectionLenKm: Array(17).fill(1.7), // 约 28.9km
  },
  line14_evening: {
    stations: ['沙田', '坑梓', '坪山围', '锦龙', '新和', '云山西路', '同乐', '红岭北', '笋岗', '红岭', '市民中心', '岗厦北', '皇岗村', '福田', '石厦', '上沙', '沙尾', '福保'],
    sectionLenKm: Array(17).fill(1.7),
  },
}

const store = useSolveStore()
const configStore = useConfigStore()
const { summary, timeseries, caseId } = storeToRefs(store)
const { config: cfg } = storeToRefs(configStore)

const chartSpace = shallowRef<echarts.ECharts>()

const activeTab = ref('space')
const hasResult = computed(() => summary.value != null && timeseries.value != null)

// ---------- 数据准备 ----------

const ts = computed<Record<string, any>>(() => timeseries.value ?? {})
const T = computed<number>(() => ts.value.t?.length ?? 0)
const dtMin = computed<number>(() => {
  const s = (cfg.value?.scenario as Record<string, unknown>)?.decision_period_min
  return typeof s === 'number' && s > 0 ? s : 15
})
const startHour = 6

function timeLabel(t: number): string {
  const m = (t - 1) * dtMin.value + startHour * 60
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}

/** 线路拓扑：config store > 算例硬编码 > 等距假设 */
const topology = computed(() => {
  // 1. config store 实际值
  const L = (cfg.value?.line as Record<string, unknown>) ?? {}
  let stations = (L.stations as string[]) ?? []
  let sectionLen = (L.section_length_km as number[]) ?? []

  // 2. 算例硬编码兜底
  const hint = TOPOLOGY_HINTS[caseId.value]
  if ((stations.length === 0 || sectionLen.length === 0) && hint) {
    stations = stations.length > 0 ? stations : hint.stations
    sectionLen = sectionLen.length > 0 ? sectionLen : hint.sectionLenKm
  }

  const M = Math.max(sectionLen.length, Object.keys(ts.value.F ?? {}).length, 1)
  const fullKm = sectionLen.reduce((a, b) => a + b, 0) > 0
    ? sectionLen.reduce((a, b) => a + b, 0)
    : typeof (L.total_length_km as number) === 'number' && (L.total_length_km as number) > 0
      ? (L.total_length_km as number)
      : M * 2.0

  const cumKm: number[] = [0]
  for (let i = 0; i < M; i++) {
    const seg = sectionLen[i] ?? (fullKm / M)
    cumKm.push(cumKm[cumKm.length - 1] + seg)
  }
  if (cumKm[cumKm.length - 1] === 0 || !isFinite(cumKm[cumKm.length - 1])) {
    cumKm.length = M + 1
    for (let i = 1; i <= M; i++) cumKm[i] = (fullKm * i) / M
  }
  const finalKm = cumKm[cumKm.length - 1] || fullKm
  const finalStations = stations.length >= M + 1 ? stations : Array.from({ length: M + 1 }, (_, i) => `S${i + 1}`)

  return {
    M,
    fullKm: finalKm,
    stations: finalStations,
    cumKm,
    sectionMid: cumKm.slice(0, -1).map((v, i) => v + (cumKm[i + 1] - v) / 2),
  }
})

const routeIds = computed<string[]>(() => Object.keys(ts.value.a ?? {}).sort())

const routeColors: Record<string, string> = {
  r0: '#1f77b4', r1: '#d62728', r2: '#2ca02c', r3: '#9467bd',
}
function routeColor(rid: string): string {
  if (routeColors[rid]) return routeColors[rid]
  let h = 0
  for (let i = 0; i < rid.length; i++) h = (h * 31 + rid.charCodeAt(i)) | 0
  return `hsl(${Math.abs(h) % 360}, 60%, 55%)`
}

const capacityC = computed<number>(() => {
  const c = (cfg.value?.line as Record<string, unknown>)?.capacity_pax
  return typeof c === 'number' && c > 0 ? c : 1400
})
const rho2 = computed<number>(() => {
  const s = (cfg.value?.scenario as Record<string, unknown>)?.crowding_rho_upper
  return typeof s === 'number' && s > 0 ? s : 1.394
})

// ---------- Tab 1：时空图 ----------

function renderSpaceTime() {
  if (!hasResult.value || !chartSpace.value) return
  const a = ts.value.a as Record<string, number[]>
  const aTotal = ts.value.a_total as number[]
  if (!aTotal || aTotal.length === 0) return

  const tIdx = Array.from({ length: T.value }, (_, i) => i + 1)
  const xLabels = tIdx.map(timeLabel)

  const seriesStacked: any[] = routeIds.value.map((rid) => ({
    name: rid,
    type: 'line',
    step: 'middle',
    stack: 'total',
    data: a[rid] ?? new Array(T.value).fill(0),
    lineStyle: { width: 1.5, color: routeColor(rid) },
    itemStyle: { color: routeColor(rid), opacity: 0.8 },
    areaStyle: { color: routeColor(rid), opacity: 0.25 },
    symbol: 'none',
    emphasis: { focus: 'series' },
  }))

  const opt: EChartsCoreOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const t = params[0]?.axisValue ?? ''
        let html = `<b>${t}</b><br/>`
        let total = 0
        for (const p of params) {
          const v = p.data ?? 0
          total += v
          html += `${p.marker} ${p.seriesName}: <b>${v}</b> 列<br/>`
        }
        html += `<hr style="margin:4px 0"/><b>合计: ${total}</b> 列`
        return html
      },
    },
    legend: { top: 0 },
    grid: { left: 55, right: 30, top: 40, bottom: 50 },
    xAxis: { type: 'category', data: xLabels, name: '时刻', nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: '在线车底（列）', minInterval: 1, axisLabel: { fontSize: 11 } },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 20, bottom: 6 }],
    series: [
      ...seriesStacked,
      {
        name: '在线合计 a_total',
        type: 'line',
        data: aTotal,
        lineStyle: { width: 2.5, color: '#dc2626' },
        itemStyle: { color: '#dc2626' },
        symbol: 'circle',
        symbolSize: 5,
        emphasis: { focus: 'series' },
      },
    ],
  }
  chartSpace.value.setOption(opt, true)
}

// ---------- 生命周期 ----------

function ensureCharts() {
  const elSpace = document.getElementById('chart-space')
  if (elSpace && !chartSpace.value) chartSpace.value = echarts.init(elSpace)
}

watch([activeTab, hasResult], () => {
  nextTick(() => {
    if (!hasResult.value) return
    ensureCharts()
    if (activeTab.value === 'space') renderSpaceTime()
  })
})

function onResize() {
  chartSpace.value?.resize()
}
window.addEventListener('resize', onResize)
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chartSpace.value?.dispose()
})

// ---------- Tab 2：动画控制 ----------

const animPlaying = ref(false)
const animStep = ref(0)
const animSubframes = 8
const animSubframe = ref(0)
let animTimer: number | null = null

function startAnim() {
  if (!hasResult.value || animPlaying.value) return
  animPlaying.value = true
  tickAnim()
}
function pauseAnim() {
  animPlaying.value = false
  if (animTimer !== null) { clearTimeout(animTimer); animTimer = null }
}
function resetAnim() {
  pauseAnim()
  animStep.value = 0
  animSubframe.value = 0
}
function gotoStep(i: number) {
  pauseAnim()
  animStep.value = Math.max(0, Math.min(T.value - 1, i))
  animSubframe.value = 0
}

function tickAnim() {
  if (!animPlaying.value) return
  animSubframe.value++
  if (animSubframe.value >= animSubframes) {
    animSubframe.value = 0
    animStep.value++
    if (animStep.value >= T.value) animStep.value = 0
  }
  animTimer = window.setTimeout(tickAnim, 120)
}
</script>

<template>
  <div class="visualize-view">
    <el-alert
      v-if="!hasResult"
      type="info"
      :closable="false"
      show-icon
      title="先去求解页跑一次求解，再来看可视化"
    />

    <template v-else>
      <!-- 动画控制条（Tab2 专属，始终显示方便跨 Tab 对比） -->
      <div class="anim-bar">
        <div class="anim-info">
          时刻：<b>{{ timeLabel(animStep + 1) }}</b>（第 {{ animStep + 1 }} / {{ T }} 步）
        </div>
        <div class="anim-controls">
          <el-button :icon="VideoPause" circle size="small" @click="pauseAnim" />
          <el-button :icon="VideoPlay" type="primary" circle size="small" @click="startAnim" />
          <el-button :icon="RefreshLeft" circle size="small" @click="resetAnim" />
          <el-slider
            v-model="animStep"
            :min="0"
            :max="T - 1"
            :step="1"
            :show-tooltip="false"
            style="width: 220px"
            @change="gotoStep"
          />
        </div>
      </div>

      <el-tabs v-model="activeTab" type="border-card">
        <!-- Tab 1：时空图 -->
        <el-tab-pane label="时空图（在线车底轨迹）" name="space">
          <div id="chart-space" class="echart-box" />
          <div class="tab-note">
            <b>验收硬标准</b>：红色粗线 = a_total 在线车底数（与后端 timeseries 精确一致）。
            各交路分段 = 堆叠 step 曲线，面积代表各时刻各交路在线规模。
          </div>
        </el-tab-pane>

        <!-- Tab 2：列车动画 -->
        <el-tab-pane label="列车在线动画" name="anim">
          <el-alert type="warning" :closable="false" show-icon class="warn-alert">
            列车<b>精确位置</b>需要引擎返回 reconstruct() 轨迹数据（始发时刻 + 交路周期）。
            前端当前采用「等距分布 + 精确在线数 a(t)」近似，联调时替换 B 引擎返回。
            但<b>在线车底数 = a_total(t) 已精确</b>，满足验收硬标准。
          </el-alert>
          <AnimCanvas
            :step="animStep"
            :subframe="animSubframe"
            :subframes="animSubframes"
            :timeseries="timeseries"
            :topology="topology"
            :route-ids="routeIds"
            :route-color="routeColor"
            :dt-min="dtMin"
          />
        </el-tab-pane>

        <!-- Tab 3 & 4：骨架先占位，后续补 -->
        <el-tab-pane label="客流 vs 运力" name="flow">
          <div class="tab-placeholder">
            待做：静态四联图（断面客流演进 / 区段列车流热力 / 峰值步断面对比 / 车底运用）。
            数据来源：timeseries.q_hat / F / a_total / x / u / s。
          </div>
        </el-tab-pane>

        <el-tab-pane label="满载率热力" name="heat">
          <div class="tab-placeholder">
            待做：静态热力图（各断面满载率，基线 1.00=定员 / 1.394=最大载客）。
            数据来源：load_rate = q_hat / (C · F)，其中 C={{ capacityC }} 人/车，ρ₂={{ rho2 }}。
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<style scoped>
.visualize-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.anim-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 14px;
  background: #f8fafc;
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
}
.anim-info {
  font-size: 14px;
  color: var(--el-text-color-primary);
}
.anim-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}
.echart-box {
  width: 100%;
  height: 420px;
}
.tab-note {
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}
.tab-placeholder {
  padding: 50px 20px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  background: #fafafa;
  border-radius: 6px;
}
.warn-alert {
  margin-bottom: 10px;
}
</style>
