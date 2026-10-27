# 结果 schema 说明（B → C 的接口）

> **版本：v1.3 ==（v2 包，2026-10-16 修订）==**　｜　**本文件是 C 开发前端唯一需要看的数据契约。**
> 示例见同目录 `示例结果_*.json`（**A 的原型跑出的真实结果**，可直接用于做图）。
> 所有结论已同步进《接口契约》§4.1–§4.5。

---

## 0 顶层结构

```json
{
  "status":        "optimal | timeout | infeasible | failed",
  "case_id":       "SZ14",
  "peak":          "morning | evening",
  "validate":      { "pass": true, "items": [ {code,name,pass,detail} ] },
  "summary":       { ... 11 项 ... },
  "timeseries":    { ... },
  "cost_terms":    { ... 5 项 *_raw ... },
  "solver":        { name, status, gap, variables, constraints, runtime_s },
  "messages":      [ ... ],
  "params_used":   { ... 8 项 ... }
}
```

★ **两层状态**：本文件的 `status` 是**求解结果态**；
`/api/task/{id}` 顶层的 `status` 是**任务态**（running/done/failed），
求解结果态在 `result_status`。**不要再写 `status_detail ?? status` 这种回退。**

---

## 1 summary（11 项，画 KPI 卡片用）

| 字段 | 类型 | 单位 | 含义 |
|---|---|---|---|
| `objective` | float | — | 归一化目标值（**跨方案可比**） |
| `cost_wait` | float | ==**人·h**== | 等待成本（==单位本次定稿==） |
| ==`cost_crowd1`== | float | 人/h | 超**定员** ρ₁ 的缺口（累计指数）；==由原 `cost_crowd` 拆出== |
| ==`cost_crowd2`== | float | 人/h | 超**最大载客** ρ₂ 的缺口 |
| `cost_km` | float | 列·km | 车公里 |
| `cost_hold` | float | 列·步 | 待班（**含准备区间**） |
| `total_wakeups` | int | 列 | 唤醒总数 |
| `max_standby` | int | 列 | 待班峰值 |
| `structure_changes` | int | 次 | 交路调整次数（★ 按 `w` 变化计，不是 `Σz`） |
| ==`peak_online`== | int | 列 | 峰值在线；==原为契约外的野字段，本次正式入契约== |
| `solve_time_s` | float | s | 求解耗时 |

---

## 2 timeseries（逐时段序列）

### ★ 三个必须注意的索引约定

| # | 约定 |
|---|---|
| 1 | **`t` 从 1 开始**：`timeseries.a[rid][t-1]` 对应第 t 步 |
| 2 | **区段键是字符串** `"1"`..`"17"`（JSON 不允许数字键），区段号从 **1** 开始 |
| 3 | **`s` 是按车场索引的字典**，与 `x`/`u`/`b` 一致 |

| 字段 | 结构 | 单位 | 含义 |
|---|---|---|---|
| `t` | `[T]` int | — | 1..T |
| `a` | `{rid: [T]}` | 列 | 各交路在线车底数 |
| `a_total` | `[T]` | 列 | Σ 各交路 |
| `x` | `{did: [T]}` | 列 | 唤醒数 |
| `u` | `{did: [T]}` | 列 | 上线数 |
| `b` | `{did: [T]}` | 列 | 待班数 |
| `s` | `{did: [T]}` | 列 | 回段数 |
| `w` | `{rid: [T]}` | 0/1 | 开行状态 |
| `z` | `[T]` | 0/1 | 结构变更指示（★ 无成本松弛，展示请改用 `w` 差分） |
| `F` | `{"m": [T]}` | **列/h** | 区段列车流 |
| `g1` | `{"m": [T]}` | **人/h** | 超定员 ρ₁ 的缺口 |
| `g2` | `{"m": [T]}` | **人/h** | 超最大载客 ρ₂ 的缺口 |
| `q_hat` | `{"m": [T]}` | **人/h** | 预测断面客流 |
| `q_true` | `{"m": [T]}` | **人/h** | 真实断面客流（出「预测 vs 真实」对比图用） |

---

## 3 时段 → 时刻

```js
function timeLabel(t) {            // t 从 1 开始
  const m = (t - 1) * 15 + 6 * 60;
  return String(Math.floor(m / 60)).padStart(2,'0') + ':' +
         String(m % 60).padStart(2,'0');
}                                   // t=1 → "06:00"   t=16 → "09:45"
```

---

## 4 cost_terms（5 项，键名统一为 `*_raw`）

`wait_raw` / `crowd1_raw` / `crowd2_raw` / `km_raw` / `hold_raw`

==`*_raw` 是本次统一的键名==：旧数据里叫 ~~`wait`~~ / ~~`km`~~，导致 mock 的 `compare()` 静默返回 0。与 `/api/compare` 的返回**同一套键名**。

★ 这些是各成本项**除以自己归一化基准之前**的原始量，量纲各不相同，
**彼此之间不能直接比大小**。

---

## 5 params_used（8 项，界面上应显示）

`tau_steps` / `u_max_tph` / `forecast_error_mape` / `forecast_error_seed` /
`weights` / `hold_cost` / `horizon_steps` / `target_peak_plan`

用于"本次结果自证是哪组参数跑出来的"。

---

## 6 派生端点

==`/api/compare` 与 `/api/sweep` 的结构见《接口契约》**§4.5 派生端点契约**——该节为本次新增，此前这两个端点没有任何契约定义。==
`/api/meta/params` 可查 `param` 的枚举词表与默认扫描值。

---

## 7 单位总表

| 量 | 单位 |
|---|---|
| 断面客流 `q_hat` / `q_true` | 人/h |
| 区段列车流 `F` | 列/h |
| 拥挤缺口 `g1` / `g2` | 人/h |
| `cost_wait` | **人·h** |
| `cost_crowd1` / `cost_crowd2` | 人/h（累计指数） |
| `cost_km` | 列·km |
| `cost_hold` | 列·步 |
