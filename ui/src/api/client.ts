import axios, { AxiosInstance } from 'axios'

// baseURL 约定：留空，各接口函数自带 /api 前缀
// dev：Vite proxy 把 /api 转到 mock:8800
// prod：同源，由 FastAPI 静态托管
// 运行时切换后端时，base 指向后端根（如 http://127.0.0.1:8800），前缀仍由接口函数提供
const DEFAULT_BASE = import.meta.env.VITE_API_BASE || ''

export const http: AxiosInstance = axios.create({
  baseURL: DEFAULT_BASE,
  timeout: 30000,
})

// 运行时切换 baseURL：联调验收时可在界面上一键 mock ↔ 真后端
export function setBaseURL(base: string) {
  http.defaults.baseURL = base
}

export function getBaseURL(): string {
  return http.defaults.baseURL || ''
}
