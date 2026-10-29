/**
 * 运行图（时空图）逐列车时刻表还原
 *
 * 依据《系统设计稿》：可视化页「数据 = /api/task/{id}/series 里的 a + 交路周期 → 前端算列车位置」，
 * 算法对照只读文件 `03_可视化算法/viz_rail.py`：
 *   reconstruct()      —— 由聚合 a(t)/T_r 积分还原每趟车始发时刻
 *   train_positions()  —— 每趟车只跑一个往返 [t_d, t_d + T_r]，跑完交给下一趟
 *
 * ★ 铁律：不能让每趟车无限循环（ph % T），否则在途车数虚高（memory.md §9 踩坑记录）。
 * ★ 本模块只做"把 a(t) 变成斜线"，不造任何客流/成本数据。
 */

/** 交路（来自 config.routings，缺省时由视图侧算例兜底表提供） */
export interface RoutingSpec {
  id: string
  /** 起点站，1 起 */
  origin: number
  /** 终点站，1 起，必须 > origin */
  terminus: number
  /** 往返周期 T_r，min */
  cycleMin: number
  /** 中文名（config.routings.name，仅用于图例标签） */
  name?: string
}

/** 视图侧已算好的线路拓扑 */
export interface TopoLike {
  M: number
  fullKm: number
  stations: string[]
  cumKm: number[]
}

export interface TimetableRoute extends RoutingSpec {
  /** 单程运行时间（含中间停站） */
  oneWayMin: number
  /** 单端折返停时（Tr = 2·单程 + 2·折返） */
  turnbackMin: number
  /** 覆盖站序号（0 起） */
  stationIdx: number[]
  /** 各覆盖站累计到达时刻（相对始发，min） */
  profileMin: number[]
}

export interface Trip {
  rid: string
  seq: number
  /** 始发时刻，min（自 06:00 起） */
  dep: number
  /** 去程折线点 [时刻 min, 站序号 0 起] */
  out: [number, number][]
  /** 回程折线点 */
  back: [number, number][]
}

export interface Timetable {
  routes: TimetableRoute[]
  trips: Trip[]
}

/** 契约 K1：单端折返周期 = 最小折返 180 s + 缓冲 120 s = 5 min（14 号线取值） */
const DEFAULT_TURNBACK_MIN = 5
/** 积分步长，与 viz_rail.reconstruct(fine=0.25) 一致 */
const FINE_MIN = 0.25
/** 单交路最多还原趟数（防异常数据把图拖垮） */
const MAX_TRIPS_PER_ROUTE = 400

/** 由 a(t) 累计积分还原始发时刻：λ(τ) = a(τ)/T_r（列/min） */
function reconstructDeps(
  aSeries: number[],
  cycleMin: number,
  horizonMin: number,
  dtMin: number,
): number[] {
  if (cycleMin <= 0 || aSeries.length === 0) return []
  const T = aSeries.length
  const lamAt = (x: number) => {
    const i = Math.min(Math.max(Math.floor(x / dtMin), 0), T - 1)
    return (aSeries[i] ?? 0) / cycleMin
  }
  const deps: number[] = []
  const n = Math.floor(horizonMin / FINE_MIN)
  let acc = 0
  let prev = lamAt(0)
  let k = 1
  for (let i = 1; i <= n; i++) {
    const cur = lamAt(i * FINE_MIN)
    const accPrev = acc
    acc += 0.5 * (prev + cur) * FINE_MIN
    prev = cur
    while (acc >= k && deps.length < MAX_TRIPS_PER_ROUTE) {
      // 在 [i-1, i] 这一小段内线性插值出第 k 趟的发车时刻
      const frac = acc > accPrev ? (k - accPrev) / (acc - accPrev) : 0
      deps.push((i - 1) * FINE_MIN + Math.min(1, Math.max(0, frac)) * FINE_MIN)
      k++
    }
    if (deps.length >= MAX_TRIPS_PER_ROUTE) break
  }
  return deps
}

/** 各站累计到达时刻：优先用配置里的逐区间运行时分，缺失时按里程等比例摊 */
function buildProfile(
  stationIdx: number[],
  cumKm: number[],
  sectionRunMin: number[] | undefined,
  oneWayMin: number,
): number[] {
  const first = stationIdx[0]
  const n = stationIdx.length
  const km = stationIdx.map((s) => cumKm[s] ?? 0)
  const lenKm = km[n - 1] - km[0]

  const usableRun =
    sectionRunMin &&
    sectionRunMin.length >= stationIdx[n - 1] &&
    sectionRunMin.slice(first, stationIdx[n - 1]).every((v) => typeof v === 'number' && v > 0)

  if (usableRun) {
    const prof = [0]
    for (let i = 1; i < n; i++) {
      prof.push(prof[i - 1] + (sectionRunMin as number[])[stationIdx[i - 1]])
    }
    return prof
  }
  if (lenKm > 0) return km.map((k) => ((k - km[0]) / lenKm) * oneWayMin)
  return stationIdx.map((_, i) => (i / Math.max(1, n - 1)) * oneWayMin)
}

/**
 * 还原时刻表。a 为 timeseries.a（{rid: [T]}），dtMin 为决策周期 Δ。
 */
export function buildTimetable(opts: {
  routes: RoutingSpec[]
  a: Record<string, number[]>
  T: number
  dtMin: number
  topo: TopoLike
  sectionRunMin?: number[]
}): Timetable {
  const { routes, a, T, dtMin, topo, sectionRunMin } = opts
  const horizonMin = T * dtMin
  const out: Timetable = { routes: [], trips: [] }

  for (const r of routes) {
    const aSeries = a[r.id]
    if (!Array.isArray(aSeries)) continue
    const oi = Math.max(0, r.origin - 1)
    const ti = Math.min(topo.cumKm.length - 1, Math.max(oi + 1, r.terminus - 1))
    if (r.cycleMin <= 0) continue

    const stationIdx: number[] = []
    for (let s = oi; s <= ti; s++) stationIdx.push(s)

    // 单程时间：有逐区间运行时分就用它，否则 Tr/2 − 折返
    let oneWayMin: number
    let turnbackMin = DEFAULT_TURNBACK_MIN
    if (
      sectionRunMin &&
      sectionRunMin.length >= ti &&
      sectionRunMin.slice(oi, ti).every((v) => typeof v === 'number' && v > 0)
    ) {
      oneWayMin = sectionRunMin.slice(oi, ti).reduce((s, v) => s + v, 0)
      turnbackMin = Math.max(0, (r.cycleMin - 2 * oneWayMin) / 2)
    } else {
      oneWayMin = Math.max(1, r.cycleMin / 2 - turnbackMin)
    }

    const profileMin = buildProfile(stationIdx, topo.cumKm, sectionRunMin, oneWayMin)
    const route: TimetableRoute = {
      ...r,
      oneWayMin,
      turnbackMin,
      stationIdx,
      profileMin,
    }
    out.routes.push(route)

    for (const dep of reconstructDeps(aSeries, r.cycleMin, horizonMin, dtMin)) {
      const outPts = stationIdx.map(
        (s, k) => [dep + profileMin[k], s] as [number, number],
      )
      const backStart = dep + oneWayMin + turnbackMin
      const backPts: [number, number][] = []
      for (let k = stationIdx.length - 1; k >= 0; k--) {
        backPts.push([backStart + (oneWayMin - profileMin[k]), stationIdx[k]])
      }
      out.trips.push({
        rid: r.id,
        seq: out.trips.filter((t) => t.rid === r.id).length + 1,
        dep,
        out: outPts,
        back: backPts,
      })
    }
  }
  return out
}
