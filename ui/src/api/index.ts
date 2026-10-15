import { http } from './client'

// 八个契约端点封装（对照 00_先读C.md §7）
// 类型先粗略标 any，待后续步骤对照结果 schema 补强

export const api = {
  /** 自检，返回可用算例 */
  health() {
    return http.get<any>('/api/health')
  },
  /** 算例列表（返回 {cases:[...]}） */
  cases() {
    return http.get<{ cases: any[] }>('/api/cases')
  },
  /** 表单字段定义（describe_config，动态生成表单） */
  schema() {
    return http.get<any>('/api/meta/schema')
  },
  /** 错误码 → 中文文案（describe_errors） */
  errors() {
    return http.get<Record<string, string>>('/api/meta/errors')
  },
  /** 建任务 → { task_id } */
  solve(payload: any) {
    return http.post<{ task_id: string }>('/api/solve', payload)
  },
  /** 进度 / 结果摘要 / 时序 */
  task(id: string) {
    return http.get<any>(`/api/task/${id}`)
  },
  /** 只要时序明细 */
  series(id: string) {
    return http.get<any>(`/api/task/${id}/series`)
  },
  /** 多方案对比 */
  compare(payload: any) {
    return http.post<any>('/api/compare', payload)
  },
  /** 敏感性扫描 */
  sweep(payload: any) {
    return http.post<any>('/api/sweep', payload)
  },
  /** 配置校验 */
  validate(payload: any) {
    return http.post<any>('/api/config/validate', payload)
  },
  /** 导出结果 */
  exportResult(id: string) {
    return http.get<any>(`/api/export/${id}.json`)
  },
}

export type Api = typeof api
