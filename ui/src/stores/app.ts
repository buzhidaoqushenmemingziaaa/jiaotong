import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getBaseURL, setBaseURL } from '@/api/client'

// 全局状态：后端环境切换 + 健康自检结果
// 验收硬标准：mock ↔ 真后端 切换时前端代码不改一行
export const useAppStore = defineStore('app', () => {
  // 当前 baseURL（mock: 空/dev proxy 或直连 mock:8800；真后端: 同源空）
  const baseURL = ref(getBaseURL())
  // 标记当前是否指向 mock（联调验收用）
  const isMock = ref(true)
  // 健康自检返回的算例列表
  const cases = ref<string[]>([])
  const lastError = ref('')

  function switchBackend(base: string, mock: boolean) {
    setBaseURL(base)
    baseURL.value = base
    isMock.value = mock
  }

  async function checkHealth() {
    try {
      const res = await import('@/api').then((m) => m.api.health())
      cases.value = res?.data?.cases ?? []
      lastError.value = ''
    } catch (e: any) {
      lastError.value = e?.message || '健康检查失败'
      cases.value = []
    }
  }

  return { baseURL, isMock, cases, lastError, switchBackend, checkHealth }
})
