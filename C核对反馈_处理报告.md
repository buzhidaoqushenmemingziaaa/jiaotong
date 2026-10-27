# 联调口径确认单（已定稿）
**定稿日期：2026-10-16**　｜　**定稿人：A（建模负责人）**　｜　**状态：8 问全部拍板**
*来源：C 的核对反馈（A_feedback_2026-10-16）。*
**_本单定稿后，C 的对比页与敏感性页可以进入最终实现。_**
*所有结论已同步进《接口契约》§4.1–§4.5。*

## 0 速览

| **#** | **问题** | **定稿结论** |
| --- | --- | --- |
| Q1 | summary 字段集 | **11 项**（原 9 项 + peak_online，cost_crowd 拆为 2 项） |
| Q2 | cost_terms 键名 | **统一为 \*_raw** |
| Q3 | cost_wait 单位 | **人·h** |
| Q4 | cost_crowd 口径 | **拆成 cost_crowd1 / cost_crowd2**，单位 **人/h** |
| Q5 | timeseries.s 类型 | **dict**（按车场索引） |
| Q6 | status 语义分层 | task.status 与 result_status **改名区分** |
| Q7 | /api/compare 返回结构 | **已写进契约 §4.5** |
| Q8 | /api/sweep 词表与结构 | **已写进契约 §4.5**，param 五值枚举 |

## Q1　summary 字段集 —— 定稿 11 项

```
{
  "objective": 0.093730,
  "cost_wait": 8506.4,
  "cost_crowd1": 156827.5,
  "cost_crowd2": 0.0,
  "cost_km": 5004.3,
  "cost_hold": 24.0,
  "total_wakeups": 25,
  "max_standby": 0,
  "structure_changes": 4,
  "peak_online": 36,
  "solve_time_s": 15.49
}
```

**为什么是 11 项而不是 10**：原 9 项里 cost_crowd 只有一个字段，
但模型有 **ρ₁（定员）与 ρ₂（最大载客）两个断点**，一个字段装不下（见 Q4）。
所以是 **9 − 1 + 2 + 1 = 11**。
**peak_online 正式入契约**（原为野字段）——它等于 max(timeseries.a_total)，是合法且好用的指标。
**验收**：三份重导后的示例结果 summary 键集合 == 上述 11 项，不缺不多。

## Q2　cost_terms 键名 —— 统一为 *_raw

```
{"wait_raw": 8506.4, "crowd1_raw": 156827.5, "crowd2_raw": 0.0,
 "km_raw": 5004.3, "hold_raw": 24.0}
```

**定这套的理由**：语义更准——这是各成本项**除以自己归一化基准之前**的原始量，
与 summary 里的 cost_* 区分开（后者是同一批数，但供 KPI 展示）。
**根因说明**：mock 的 compare() 原本就按 *_raw 写，
而示例数据是裸名 wait/km → .get(...,0) 兜底 → **静默显示 0**。
**是数据旧了，不是 mock 写错了。** 现已统一。
**验收**：compare() 返回的 wait_raw / km_raw **非 0**
（line14_morning 应为 8506.4 / 5004.3）。

## Q3　cost_wait 单位 —— 人·h
**定稿依据**：4 小时高峰 8506 这个量级对人·h 自洽；若是人·min 应约 51 万。
**换算依据（写进图注用）**：

```
cost_wait = Σ_t Σ_g q̄(t,g) × (Δ/60) × H(t,g)/2 / 60     单位 人·h
  其中 q̄ 为服务组候车人数（人/h），H 为合并发车间隔（min）
```

⚠️ **在此之前 C 不得跨来源混用** mock 值与引擎值——否则会静默差 60 倍。
**现已定死为单一单位，风险解除。**

## Q4　cost_crowd —— 拆成两项

| **字段** | **口径** | **单位** |
| --- | --- | --- |
| cost_crowd1 | Σ{t}Σ{m} max(0, q̂ − ρ₁·C·F)，ρ₁ = 1.0（**定员**） | 人/h |
| cost_crowd2 | Σ{t}Σ{m} max(0, q̂ − ρ₂·C·F)，ρ₂ = 1.394（**最大载客**） | 人/h |

**单位说明**：每个 g 的瞬时量纲是 **人/h**；对时段与区段求和后是一个**累计指数**，
不是可直接解释的物理量。**UI 只用于相对比较**，不要标注成"人"或"人·h"。
**为什么必须拆**：用 toyline 算例验证——crowd1 = 1082351.29，
crowd1 + crowd2 = 1958553.15，**两者差 1.81 倍**。
合并成一个字段会丢失"超出最大载客"这一严重等级的区分度。

## Q5　timeseries.s —— dict

```
"s": {"D1": [0,0,...], "D2": [0,0,...]}
```

**与 x / u / b 一致**（都是按车场索引的字典）。
**根因**：契约 §4.2 表格原写 list[int]，schema 说明写 dict，数据是 dict——**文档内部打架**。
现已把契约那一行改成 dict。

## Q6　status 两层语义 —— 改名区分

| **层** | **字段** | **取值** | **在哪** |
| --- | --- | --- | --- |
| **任务态** | task.status | running / done / failed | /api/task/{id} 顶层 status |
| **求解结果态** | result_status | optimal / timeout / infeasible / failed | 同上，**改名为 result_status** |

**改名的理由**：原来 mock 用 status_detail，与 status 并列看起来像"补充说明"，
语义不清晰。result_status 一眼能看出是"求解结果的状态"。
**这样 C 不再需要 status_detail ?? status 的猜测式回退。**
**验收**：一个 done 任务，**一处**就能取到 optimal。

## Q7　/api/compare 返回结构 —— 已写入契约 §4.5

```
{
  "case": "line14_morning",
  "base_variant": "v0",
  "rows": [
    { "variant_id": "v0", "name": "三级嵌套",
      "objective": 0.093730,
      "wait_raw": 8506.4, "crowd1_raw": 156827.5,
      "crowd2_raw": 0.0, "km_raw": 5004.3, "hold_raw": 24.0,
      "peak_online": 36, "relative_pct": 0.00 }
  ]
}
```

**三个新增/明确项**：
1. **variant_id**（原只有 name）——方案多时便于稳定标识；
1. **base_variant** ——明确 relative_pct 的零点；
1. **relative_pct 口径** = (本方案 objective − base 方案 objective) / base 方案 objective × 100。
**\*_raw 与 cost_terms 同一套键名**（Q2 联动）。

## Q8　/api/sweep 词表与结构 —— 已写入契约 §4.5

### 修掉的两个 bug

| **#** | **原实现** | **后果** | **现修法** |
| --- | --- | --- | --- |
| 1 | 用 param 去查算例表，且完全忽略 case | 传不同算例返回**逐字节相同** | **case 生效** |
| 2 | param 取值三方打架 | 不知道能传什么 | **五值枚举**，非法值返回 E4001 |

### param 枚举（与契约 §3.8 对齐）

```
mape | tau_steps | umax_tph | cbd_scale | alpha
```

### 返回结构

```
{
  "case": "line14_morning",
  "param": "mape",
  "param_label": "预测误差 MAPE",
  "x_unit": "—",
  "points": [
    { "x": 0.05, "objective": 0.091479,
      "regret_static": 1.00, "regret_rolling": 0.07 }
  ]
}
```

### regret_* 口径（原来完全没定义）

```
regret = (该策略实际成本 − 完美预测基准) / 完美预测基准 × 100     单位 %
```

基准 = 同算例下用**真值需求**一次求解的结果。
**验收**：传 line14_morning 与 toyline_morning 得到**不同**结果
（已实测：0.0909 vs 2.1207）。

## 附录　本轮同时修掉的材料问题（原附录 A）

| **#** | **问题** | **现状** |
| --- | --- | --- |
| A1 | 示例_describe_config.json 只有 3 字段 | ✅ **补到 7 组 / 42 字段**，每项含 key/label/type/unit/required/editable/doc |
| A2 | 错误码两套 | ✅ **统一为契约 §7 的 13 个码**（E1001–E4001） |
| A3 | 配套文件缺失 | ✅ 已补（见包内 05_配套文件/） |
| A4 | q_true 全缺 | ✅ **三份示例结果都已补** |
| A5 | __pycache__ 残留 | ✅ **已删** |

## 一句话
**_8 问全部定稿，并已同步进《接口契约》§4.1–§4.5。_**

_**C 的对比页与敏感性页现在有契约保护了**——此前这两个端点连参照物都没有，_
*是比 summary 更危险的一处缺口。*
