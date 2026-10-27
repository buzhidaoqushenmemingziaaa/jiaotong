<script setup lang="ts">
/**
 * 列车在线动画 Canvas
 *
 * ★ 在线车底数精确 = a(t, rid)（验收硬标准）；
 *   位置近似 = 均匀分布 + 相位扰动（联调时替换 B 引擎返回的 reconstruct() 轨迹）。
 */
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  step: number
  subframe: number
  subframes: number
  timeseries: Record<string, any> | null
  topology: {
    M: number
    fullKm: number
    stations: string[]
    cumKm: number[]
    sectionMid: number[]
  }
  routeIds: string[]
  routeColor: (rid: string) => string
  dtMin: number
}>()

const canvas = ref<HTMLCanvasElement | null>(null)

/** 各交路当前步的在线车底数 */
const aAt = computed(() => {
  const a = props.timeseries?.a ?? {}
  const result: Record<string, number> = {}
  for (const rid of props.routeIds) {
    const arr = a[rid] as number[]
    result[rid] = arr?.[props.step] ?? 0
  }
  return result
})
const totalAt = computed(() => {
  const a = props.timeseries?.a_total as number[]
  return a?.[props.step] ?? 0
})

function draw() {
  const c = canvas.value
  if (!c) return
  const ctx = c.getContext('2d')!
  const W = c.width
  const H = c.height
  ctx.clearRect(0, 0, W, H)

  // 布局
  const padX = 60
  const padY = 28
  const lineW = W - padX * 2
  const nLanes = Math.max(props.routeIds.length, 1)
  const laneH = 40
  const gapY = 20
  const totalLanesH = nLanes * laneH + (nLanes - 1) * gapY
  const baseY = (H - totalLanesH) / 2 + laneH / 2
  const fullKm = props.topology?.fullKm ?? 30

  const kmToX = (km: number) => padX + (km / fullKm) * lineW

  // 画里程刻度
  ctx.strokeStyle = '#ddd'
  ctx.fillStyle = '#999'
  ctx.font = '11px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'
  const cum = props.topology?.cumKm ?? []
  const stations = props.topology?.stations ?? []
  for (let i = 0; i < cum.length; i++) {
    const x = kmToX(cum[i])
    ctx.beginPath()
    ctx.moveTo(x, baseY - 12)
    ctx.lineTo(x, baseY + totalLanesH + 12)
    ctx.stroke()
    const sName = stations[i] ?? `S${i + 1}`
    ctx.fillText(sName, x, baseY + totalLanesH + 18)
  }

  // 线路底色
  props.routeIds.forEach((rid, idx) => {
    const laneY = baseY + idx * (laneH + gapY)
    const col = props.routeColor(rid)
    ctx.strokeStyle = col + '30'
    ctx.lineWidth = 4
    ctx.beginPath()
    ctx.moveTo(kmToX(0), laneY)
    ctx.lineTo(kmToX(fullKm), laneY)
    ctx.stroke()
    // 交路标签
    ctx.fillStyle = props.routeColor(rid)
    ctx.font = 'bold 12px sans-serif'
    ctx.textAlign = 'right'
    ctx.textBaseline = 'middle'
    const n = aAt.value[rid] ?? 0
    ctx.fillText(`${rid}`, padX - 10, laneY)
  })

  // ★ 画列车：精确数量 a(rid, t)，近似位置
  const phase = (props.step * props.dtMin + props.subframe * props.dtMin / Math.max(1, props.subframes)) / 60
  props.routeIds.forEach((rid, idx) => {
    const laneY = baseY + idx * (laneH + gapY)
    const col = props.routeColor(rid)
    const n = aAt.value[rid] ?? 0
    const trainW = Math.max(10, lineW * 0.018)
    const trainH = 14

    for (let i = 0; i < n; i++) {
      const basePos = (i + 0.5) / Math.max(1, n)
      const jitter = Math.sin(phase * 2 + i * 1.7) * 0.05
      const xRatio = Math.max(0.02, Math.min(0.98, basePos + jitter))
      const x = kmToX(xRatio * fullKm)

      ctx.fillStyle = col
      ctx.fillRect(x - trainW / 2, laneY - trainH / 2, trainW, trainH)
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 1
      ctx.strokeRect(x - trainW / 2, laneY - trainH / 2, trainW, trainH)
    }
  })

  // 标题栏
  ctx.fillStyle = '#333'
  ctx.font = 'bold 14px sans-serif'
  ctx.textAlign = 'right'
  ctx.textBaseline = 'top'
  const hour = 6 + Math.floor((props.step * props.dtMin) / 60)
  const min = (props.step * props.dtMin) % 60
  const timeStr = `${String(hour).padStart(2, '0')}:${String(min).padStart(2, '0')}`
  ctx.fillText(
    `时刻 ${timeStr}　|　在线合计 a_total = ${totalAt.value} 列`,
    W - padX,
    padY - 8,
  )
  // 图例提示
  ctx.textAlign = 'left'
  ctx.font = '11px sans-serif'
  ctx.fillStyle = '#999'
  ctx.fillText('★ 在线车底数精确 = a_total(t)，位置近似分布', padX, padY - 8)
}

function resize() {
  const c = canvas.value
  if (!c) return
  const parent = c.parentElement
  if (!parent) return
  const dpr = window.devicePixelRatio || 1
  const w = parent.clientWidth
  const h = Math.max(320, Math.min(520, parent.clientHeight || 400))
  c.width = w * dpr
  c.height = h * dpr
  c.style.width = w + 'px'
  c.style.height = h + 'px'
  const ctx = c.getContext('2d')
  if (ctx) ctx.scale(dpr, dpr)
  draw()
}

watch(
  () => [props.step, props.subframe, props.timeseries, props.routeIds],
  () => requestAnimationFrame(draw),
  { deep: true },
)

onMounted(() => {
  resize()
  window.addEventListener('resize', resize)
})
onUnmounted(() => window.removeEventListener('resize', resize))
</script>

<template>
  <canvas ref="canvas" class="anim-canvas" />
</template>

<style scoped>
.anim-canvas {
  width: 100%;
  height: 400px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
}
</style>
