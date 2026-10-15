<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { getBaseURL } from '@/api/client'

// 自检项：逐个调用契约端点，验证「接口层 → proxy → Mock」链路是否通
type CheckItem = {
  name: string
  path: string
  status: 'pending' | 'running' | 'ok' | 'fail'
  detail: string
}

const baseURL = ref(getBaseURL())
const running = ref(false)
const checks = ref<CheckItem[]>([
  { name: '健康自检', path: 'GET /api/health', status: 'pending', detail: '' },
  { name: '算例列表', path: 'GET /api/cases', status: 'pending', detail: '' },
  { name: '表单 schema', path: 'GET /api/meta/schema', status: 'pending', detail: '' },
  { name: '错误码文案', path: 'GET /api/meta/errors', status: 'pending', detail: '' },
])

const schemas = ref<any>(null)

function reset() {
  checks.value.forEach((c) => {
    c.status = 'pending'
    c.detail = ''
  })
  schemas.value = null
}

async function run(name: string, fn: () => Promise<any>, summarize: (d: any) => string) {
  const item = checks.value.find((c) => c.name === name)!
  item.status = 'running'
  try {
    const res = await fn()
    item.status = 'ok'
    item.detail = summarize(res?.data)
  } catch (e: any) {
    item.status = 'fail'
    item.detail = e?.response?.status
      ? `HTTP ${e.response.status}`
      : e?.message || '请求失败'
  }
}

async function runAll() {
  if (running.value) return
  running.value = true
  reset()
  baseURL.value = getBaseURL()
  const started = Date.now()

  await run('健康自检', () => api.health(), (d) => `ok=${d?.ok} · 算例 ${d?.cases?.length ?? 0} 个`)
  await run('算例列表', () => api.cases(), (d) => {
    const arr = Array.isArray(d) ? d : d?.cases || []
    return `共 ${arr.length} 个：${arr.map((x: any) => x.id).join(', ')}`
  })
  await run(
    '表单 schema',
    () => api.schema(),
    (d) => {
      schemas.value = d
      const n = (d?.groups || []).reduce((s: number, g: any) => s + (g.fields?.length || 0), 0)
      return `${d?.groups?.length ?? 0} 组 · ${n} 个字段`
    },
  )
  await run('错误码文案', () => api.errors(), (d) => `${Object.keys(d || {}).length} 条错误码`)

  running.value = false
  const passed = checks.value.filter((c) => c.status === 'ok').length
  if (passed === checks.value.length) {
    ElMessage.success(`全部通过（${Date.now() - started} ms）`)
  } else {
    ElMessage.warning(`通过 ${passed}/${checks.value.length}`)
  }
}

onMounted(() => {
  baseURL.value = getBaseURL()
  runAll()
})

const tagType = (s: CheckItem['status']) =>
  ({ pending: 'info', running: 'warning', ok: 'success', fail: 'danger' }[s] as any)
const tagText = (s: CheckItem['status']) =>
  ({ pending: '待运行', running: '运行中', ok: '通过', fail: '失败' }[s])
</script>

<template>
  <div class="test-page">
    <el-card shadow="never">
      <div class="bar">
        <div class="bar-left">
          <span class="label">当前 baseURL</span>
          <el-tag type="info" effect="plain">{{ baseURL || '(同源 / 走 Vite proxy)' }}</el-tag>
        </div>
        <el-button type="primary" :loading="running" @click="runAll">运行自检</el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="mt">
      <el-table :data="checks" stripe>
        <el-table-column prop="name" label="检查项" width="160" />
        <el-table-column prop="path" label="端点" width="260">
          <template #default="{ row }">
            <code>{{ row.path }}</code>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="tagType(row.status)" size="small">{{ tagText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="结果" />
      </el-table>
    </el-card>

    <el-card v-if="schemas" shadow="never" class="mt">
      <template #header>表单 schema（describe_config 动态返回）</template>
      <el-collapse>
        <el-collapse-item
          v-for="g in schemas.groups"
          :key="g.id"
          :title="`${g.title}（${g.fields?.length || 0} 字段）`"
          :name="g.id"
        >
          <el-table :data="g.fields" size="small" stripe>
            <el-table-column prop="key" label="key" width="220" />
            <el-table-column prop="label" label="label" width="180" />
            <el-table-column prop="type" label="type" width="120" />
            <el-table-column prop="unit" label="unit" width="80" />
            <el-table-column label="必填" width="70">
              <template #default="{ row }">{{ row.required ? '是' : '否' }}</template>
            </el-table-column>
            <el-table-column label="可编辑" width="80">
              <template #default="{ row }">{{ row.editable ? '是' : '只读' }}</template>
            </el-table-column>
            <el-table-column prop="doc" label="说明" />
          </el-table>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<style scoped>
.test-page {
  display: flex;
  flex-direction: column;
}
.mt {
  margin-top: 16px;
}
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.bar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.label {
  color: #606266;
  font-size: 14px;
}
code {
  font-family: Consolas, Monaco, monospace;
  color: #177cff;
}
</style>
