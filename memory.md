# 项目记忆（C 角色 · 前端开发）

> 作用：给后续会话快速恢复上下文。看这一份就能开工。
> 更新日期：2026-10-16

---

## 1 我是谁 / 边界

- **角色**：C（系统与产品），写界面 + 与 B 对接。
- **并行开发**：B 写 `engine/` + `run_case.py`；我写 `ui/`（Web 版 = Vue3 前端 + FastAPI 后端壳）。
- **唯一对接点**：`run_case.py` 的三个函数 + 一份《接口契约》。改字段必须双方签字。
- **铁律**：① 引擎不依赖界面；② 界面不建模型；③ 结果靠返回值传递。

## 2 不可修改（只读 / 调用）

- `01_数据契约/`（结果 schema + 真实示例 + 表单/错误定义）
- `03_可视化算法/viz_rail.py`
- `04_Mock后端/`
- `00_先读C.md`、`C工期估算.md`
- 严格遵守《数据契约》《设计文档》开发。

## 3 技术栈

- 前端：Vue3 + Vite + Element Plus + ECharts
- 后端：FastAPI（与 engine 同语言，零阻抗，原样复用 `run_case.py`）
- 部署：单进程（uvicorn + vite build 由 FastAPI StaticFiles 托管），**禁用微服务/K8s/Celery+Redis**
- 异步：BackgroundTasks + SQLite 任务表 + 前端轮询（**不用回调，用轮询**）

## 4 八大功能模块

1. 线路建模（表单/Excel 导入）
2. 参数配置（**schema 驱动表单，禁止手抄字段**）
3. 方案求解（异步任务 + 进度 + 日志）
4. 运行可视化（动画 / 时空图 / 满载率热力 / 客流 vs 运力）
5. 方案对比
6. 敏感性分析（τ / 配属 / 需求倍数 / cbd_scale / 权重扫描）
7. 报告导出（docx/pdf）
8. 诊断与帮助（瓶颈定位）

## 5 Mock 后端（现在就能用）

- 启动：`python 04_Mock后端/mock_server.py --delay 4` → http://127.0.0.1:8800
- 已带 CORS，Vite :5173 可直接跨域调用。
- `--delay 4` 故意慢，逼前端按"慢操作"设计；B 引擎就位后只换 baseURL，**前端代码不改一行**（硬验收标准）。

### 8 个端点
| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/health` | 自检 |
| GET | `/api/cases` | 算例列表 |
| GET | `/api/meta/schema` | 表单字段定义（动态生成表单） |
| GET | `/api/meta/errors` | 错误码 → 中文 |
| POST | `/api/solve` | 建任务 → `{task_id}` |
| GET | `/api/task/{id}` | 进度/结果摘要/时序 |
| GET | `/api/task/{id}/series` | 时序明细 |
| POST | `/api/compare` | 方案对比 |
| POST | `/api/sweep` | 敏感性扫描 |
| POST | `/api/config/validate` | 配置校验 |
| GET | `/api/export/{id}.json` | 导出 |

## 6 results 顶层字段（results dict）

`status` · `case_id` · `peak` · `validate` · `summary` · `timeseries` · `cost_terms` · `solver` · `messages` · `params_used`

### 6.1 summary（KPI 卡）
`objective` · `cost_wait`(人·h) · `cost_crowd`(人/h) · `cost_km`(列·km) · `cost_hold`(列·步) · `total_wakeups` · `max_standby` · `structure_changes` · `solve_time_s`

### 6.2 timeseries（长度均 = horizon_steps=16）
`t` · `a{rid}` · `a_total` · `x{did}` · `u{did}` · `b{did}` · `s{did}` · `w{rid}` · `z` · `F{"m"}` · `g1{"m"}` · `g2{"m"}` · `q_hat{"m"}` · `q_true{"m"}`

### 6.3 ★ 三个索引坑（已踩过）
1. **`t` 从 1 开始**：`timeseries.a[rid][t-1]` 才是第 t 步
2. **区段键是字符串**：`F`/`g1`/`g2`/`q_hat` 键 = `"1".."17"`（JSON 不许数字键），区段从 1 起
3. **`s` 是按车场字典**（与 x/u/b 一致），不是列表

### 6.4 单位（最易错）
- `q_hat`：人/h（非人/步）
- `F`：列/h
- `g1`/`g2`：人/h
- `wait_raw`：人·h；`km_raw`：列·km；`hold_raw`：列·步
- `cost_terms` 各项量纲不同，**不可直接比大小**；`objective` 是归一加权和，跨方案才可比。

### 6.5 时刻换算
Δ=15min，起点 06:00：`t=1 → "06:00"`，`t=16 → "09:45"`。
`timeLabel(t) = pad2(floor((t-1)*15+360)/60) + ':' + pad2((t-1)*15 % 60)`

## 7 表单 schema 形状

`GET /api/meta/schema` → `describe_config()` 返回：
```json
{ "groups": [ { "id": "...", "title": "...", "fields": [
  { "key": "line.stations", "label": "...", "type": "list[str]",
    "unit":"", "required": true, "editable": true/false, "doc": "..." } ] } ] }
```
- `editable:false` 渲染为只读（如线路全长、ρ2，由引擎派生）
- C 只做查表渲染，**不许自己写校验逻辑、不许编中文文案**

## 8 错误码（C 只查表渲染）
- `E_CONFIG_MISSING`：配置缺少必填字段
- `E_INFEASIBLE`：约束冲突，无可行解
- `E_TIMEOUT`：求解超时
- 完整码见 `01_数据契约/示例_describe_errors.json`

## 9 可视化算法坑（★最难一项）

`03_可视化算法/viz_rail.py` 提供 `route_profile()` / `reconstruct()` / `train_positions()` 三个函数：从聚合解（`a[t][r]` + 交路周期 T）还原逐列车轨迹。

**最大坑**：不能让每趟车无限循环（`ph % T`），否则在途车数虚高（A 第一版踩过）。每趟车跑完一个往返 `[t_d, t_d+T]` 后交给下一趟。

**归属**：算法建议放 B 的 `engine/viz.py`，C 只渲染。否则论文图与系统图对不上。**联调时必须问清 B**。

## 10 风险与里程碑

### 工期
- MVP ≈ 24 人日 / 完整版 ≈ 40 人日
- M1 骨架(3) → M2 主流程(6, 可演示) → M3 可视化(6) → M4 对比扫描(5) → M5 收尾(4)
- 时间紧时优先保 M1–M3（≈15 人日），砍 M4
- 可省 8–12 人日：现成 admin 模板 / JSON Schema 驱动表单 / ECharts 现成类型 / Mock 开发 / D 在 W6 后支援

### 三大风险
1. **列车运行动画**（3 人日，演示门面）：ECharts 无现成类型，要自绘；用静态时空图保底
2. **联调**（4 人日，常翻倍）：字段/索引对不上；对策——接 Mock 开发，疑问当场问 A
3. **C 单人**：D 在 W6 后转支援前端

## 11 验收硬标准（前端做完了）

- [ ] Mock 能跑通：选算例 → 配置 → 求解 → 看动画 → 对比 → 导出
- [ ] baseURL 从 mock 换真后端，**前端代码不改一行**
- [ ] 表单由 `describe_config()` 动态生成，无手抄字段
- [ ] 错误提示来自 `describe_errors()`，无自编中文
- [ ] 动画在线车底数与 `timeseries.a_total` 一致

## 12 与 B 联调必问 4 件事

1. `progress_cb` 的确切签名（若用回调）——**建议用轮询，不用回调**
2. 能否并发求解？CBC 单线程，要不要排队？——按单任务队列设计
3. 不可行/超时时 `status` 是啥？`timeseries` 还有没有？——按 `{status:"failed", messages:[...]}` 处理
4. `engine/viz.py` 归谁？图表算法两边必须一致

## 13 关键路径 / 文件

| 路径 | 用途 |
|---|---|
| `00_先读C.md` | C 角色开工指南（必读） |
| `C工期估算.md` | 工期/风险/里程碑 |
| `02_设计文档/系统设计稿.md` | 系统架构、接口清单、分工排期 |
| `02_设计文档/...接口契约.md` | B/C 唯一对接契约（字段冻结） |
| `01_数据契约/结果schema说明.md` | C 开发前端唯一需要看的数据契约 |
| `01_数据契约/示例结果_*.json` | 前端 mock 数据（A 原型真实结果） |
| `01_数据契约/示例_describe_config.json` | 表单 schema 源 |
| `01_数据契约/示例_describe_errors.json` | 错误码 → 中文 |
| `03_可视化算法/viz_rail.py` | 列车轨迹还原算法 |
| `04_Mock后端/mock_server.py` | Mock 后端（零依赖） |

## 14 一句话

> 不等 B 也能把前端全流程做出来。数据契约 + 真实示例 + Mock + 可视化算法都齐了。
> **按"求解是慢操作"设计，用轮询不用回调，baseURL 可切换**，B 什么时候来都能无缝接上。

## 15 变更日志

- 搭好 ui 前端工程脚手架（Vue3+Vite+EP+路由）
- 修 /api 重复前缀：env 留空，路径自带 /api
- 新增"测试运行"页，自检四端点全通过
- 拆解第3步为3.1~3.7七小步
- 3.1完成：fieldTypes.ts类型映射
- 3.2完成：FieldRenderer控件组件
- 3.3完成：分组折叠面板+栅格布局
- 3.4完成：config store 嵌套结构
- 3.5完成：必填校验规则自动生成
- 3.6完成：校验提交+错误码查表
- 3.7完成：配置页闭环自测（第3步7/7完）
在执行第三步时，browser 子代理三次"预算耗尽"并非操作失败 —— 它两次只用了 8/60、17/60 步就报耗尽。真实原因是 它的报告输出过长被截断 。这个故障模式对后续第 6 步（列车动画，最难的 3.0 人日项）很有用：派验证任务时要压短报告长度。
- 拆解第4步为4.1~4.6六小步
- 4.1完成：solve store状态机
- 4.2完成：轮询器内置store防重入
- 4.3完成：求解页提交表单
- 4.4完成：进度条+日志面板
- 4.5完成：done摘要+failed查表（杀mock实测）
- 4.6完成：求解页闭环自测（第4步6/6完）
- 5完成：结果总览页KPI卡片+溯源（第5步1/1）
- ★第5步发现契约不一致（已于 v2 定稿解决，见 §16）
- v2契约修订要点已归档
- v2文件已同步正式目录并实测通过
- ★前端v2契约对齐：ResultsView cost_crowd拆crowd1/crowd2、solver variables/constraints、result_status优先读、costRows简化；solve.ts加resultStatus/validate；api补metaParams；Mock实测全部通过
- ConfigView错误表item.field→item.name，validate面板ResultsView可折叠展示V1-V8校验详情
- vue-tsc全量零错误，Mock回包11字段summary、result_status、solver6字段、validate全部对齐
- ★第6步列车运行动画骨架完成：VisualizeView四Tab容器（时空图step堆叠+a_total红线验收硬标准、AnimCanvas近似位置动画精确在线数、客流vs运力/热力骨架占位）；vue-tsc零错误，浏览器5/5通过
- 架构决策：viz_rail.py的reconstruct()依赖引擎Case对象（线路里程/交路周期Tcyc）不在timeseries里，前端暂用「聚合精确+位置近似」，联调时替换B返回的精确轨迹
- AdvisorTool收尾：roundRect→fillRect兼容旧浏览器；三个算例硬编码线路拓扑（toyline A-F 6站、line14深圳18站）；routeColor hash公式修正；solve store加caseId字段
第6步bug修复：
-watch 增加 timeseries 依赖：时空图白屏 —— 从"先求解再进可视化"的路径进来时 watch 完全不跑，ECharts 实例从未初始化。
-加 onMounted： 不管用户怎么进入 VisualizeView，只要组件挂载了就保证`ensureCharts()` 和`renderSpaceTime()` 至少跑一次。
-动画按钮加组件存活门禁：点播放没反应 —— 动画逻辑在跑但渲染组件不存在
---

## 16 v2 契约修订（2026-10-17 负责人定稿，替代 §6.1/§6.2/§8 旧描述）

来源：负责人回传的修订文件（修订说明_v2.md + C核对反馈_处理报告.md）。裁定原则：**改数据不改文档**（数据补齐对齐文档）。以下为开发唯一口径。

> ✅ **2026-10-17 已将 v2 全部文件覆盖同步到正式目录**（01_数据契约/、02_设计文档/、04_Mock后端/、00_先读C.md、C工期估算.md，新增 05_配套文件/；两份说明文档留在项目根），Mock 已重启并实测：result_status=optimal、summary 11 字段、cost_terms *_raw、solver.variables/constraints、/api/meta/params 全部生效。轨道交通v2 临时文件夹可删。

**两个反馈问题的裁定**
- `summary` 定 **11 字段**：objective / cost_wait（单位定 **人·h**）/ **cost_crowd1 / cost_crowd2**（原 cost_crowd 拆成超定员、超最大载客两项）/ cost_km / cost_hold / total_wakeups / max_standby / structure_changes / **peak_online**（原契约外野字段，正式入契）/ solve_time_s
- `cost_terms` 键定稿：`wait_raw / crowd1_raw / crowd2_raw / km_raw / hold_raw`

**其他契约变更**
- `solver` 6 字段：name / status / gap / **variables / constraints**（旧 nvars/ncons 作废）/ runtime_s
- `timeseries`：`s` 明确为 dict{did}（不是 list）；新增 `q_true`（真实客流，给「预测 vs 真实」图）
- 任务回包：`status_detail` → **`result_status`**（求解结果态读它，不写 `?? status` 回退）；task 回包新增 validate
- **新增端点** `GET /api/meta/params`；无端点删除，所有路径与请求体不变（/api/solve、task/{id}、series 等照旧）
- mock 修两 bug：compare 不再静默返 0（回包 `{case, base_variant, rows:[{variant_id, *_raw, objective, peak_online, relative_pct}]}`）；sweep 的 case 参数生效，新增 param_label/x_unit，非法 param 返 E4001
- describe_config：2 组 3 字段 → **7 组 42 字段**；新类型 `list[object]`、`dict[str,list[float]]`（fieldTypes 无映射，走只读兜底）
- describe_errors：改为 **13 个错误码 E1001~E4001**（旧 3 码作废）
- validate item 形态 `{code, name, pass, detail}`（无 field 字段）
- health 加 version、cases 加 peak_online（纯增量）

**前端待改（继续开发时先做）**
1. ~~ResultsView：cost_crowd 卡拆成 cost_crowd1/cost_crowd2 两张；solver 的 nvars/ncons 改读 variables/constraints~~ ✅已完成 2026-10-27（含 result_status 优先读、costRows 简化为 *_raw、solver 补 status/gap/runtime_s、solve.ts 加 resultStatus/validate、api 补 metaParams）
2. ~~ConfigView 错误表：字段名列从 item.field 改读 item.name~~ ✅已完成 2026-10-27（validate 面板 ResultsView 可折叠展示）
3. 第 8 步 compare/sweep 开工时直接按新回包字段写（variant_id / *_raw / param_label / x_unit）

**遗留待向负责人确认**
- 接口契约 §4 顶层 status 枚举仍只写 optimal/infeasible/timeout，漏 schema 说明里的 "failed"
- 环境：Python 3.13.5；PuLP 必须钉 **3.3.2**（4.0.0 wheel 不含 CBC）；Windows 读写显式 encoding=utf-8