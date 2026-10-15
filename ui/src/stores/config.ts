import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/api'
import {
  type ConfigSchema,
  type FieldDef,
  initialValueOf,
} from '@/components/config/fieldTypes'

/**
 * 3.4 产出：参数配置 store
 *
 * 关键设计：
 *  1. schema 里的 key 是点分路径（`line.stations`），但提交给引擎的 config 必须是
 *     **嵌套结构**（`{"line": {"stations": [...]}}`）——
 *     由 mock 的 `/api/config/validate` 读 `cfg.line.stations` 可确认。
 *     所以此处用 setByPath/getByPath 做两套表示之间的转换。
 *  2. ★ 契约 §1.5：配置里 `_` 开头的键（`_placeholders`、`_note`）是给人看的说明，
 *     必须原样保留。实现上靠"整体接收、不重建对象"，setValue 只写目标路径。
 */

/** 点分路径读：`line.stations` → obj.line.stations */
function getByPath(obj: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((acc, k) => {
    if (acc === null || typeof acc !== 'object') return undefined
    return (acc as Record<string, unknown>)[k]
  }, obj)
}

/** 点分路径写；路径上缺中间层就补 {} */
function setByPath(obj: Record<string, unknown>, path: string, value: unknown) {
  const keys = path.split('.')
  let cur: Record<string, unknown> = obj
  for (let i = 0; i < keys.length - 1; i++) {
    const k = keys[i]
    if (cur[k] === null || typeof cur[k] !== 'object') cur[k] = {}
    cur = cur[k] as Record<string, unknown>
  }
  cur[keys[keys.length - 1]] = value
}

export const useConfigStore = defineStore('config', () => {
  /** describe_config() 返回的分组字段定义 */
  const schema = ref<ConfigSchema>({ groups: [] })
  /** 真正的配置对象（嵌套结构，可直接提交给引擎） */
  const config = ref<Record<string, unknown>>({})
  const loading = ref(false)
  const error = ref('')

  /** 全部字段（拍平，便于遍历） */
  const fields = computed<FieldDef[]>(() =>
    schema.value.groups.flatMap((g) => g.fields),
  )
  const hasSchema = computed(() => schema.value.groups.length > 0)

  /**
   * 拉 schema 并用默认值初始化 config。
   * 已加载过则直接返回（切页回来不重复请求，且用户已改的值不会丢）。
   */
  async function loadSchema(): Promise<void> {
    if (hasSchema.value || loading.value) return
    loading.value = true
    error.value = ''
    try {
      const res = await api.schema()
      schema.value = (res.data ?? { groups: [] }) as ConfigSchema
      initFromSchema()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'schema 拉取失败'
    } finally {
      loading.value = false
    }
  }

  /** 用 schema 自带的 default 初始化一个空 config（没有 default 的走空值） */
  function initFromSchema() {
    const next: Record<string, unknown> = {}
    for (const f of fields.value) setByPath(next, f.key, initialValueOf(f))
    config.value = next
  }

  /**
   * 用一份已有 config 初始化（如算例自带的完整配置）。
   * ★ 整体接收、不重建 —— `_` 开头的说明键由此原样保留（契约 §1.5）。
   */
  function initFromConfig(cfg: Record<string, unknown>) {
    config.value = cfg ?? {}
  }

  /** 读单字段值（FieldRenderer 的 :model-value 用） */
  function getValue(key: string): unknown {
    return getByPath(config.value, key)
  }

  /** 写单字段值（FieldRenderer 的 update:model-value 用），只动目标路径 */
  function setValue(key: string, value: unknown) {
    setByPath(config.value, key, value)
  }

  /** 恢复为 schema 默认值 */
  function reset() {
    initFromSchema()
  }

  /**
   * 提交给引擎的载荷：原样深拷贝。
   * C 不替引擎做业务过滤——editable:false 的派生字段照常带上，由引擎自己算。
   */
  function toPayload(): Record<string, unknown> {
    return JSON.parse(JSON.stringify(config.value)) as Record<string, unknown>
  }

  // ---------- 3.6 错误码查表 ----------

  /** 错误码 → 中文（来自 describe_errors()）。契约要求 C 只查表渲染，不编文案 */
  const errorMap = ref<Record<string, string>>({})

  async function loadErrors(): Promise<void> {
    if (Object.keys(errorMap.value).length > 0) return
    try {
      const res = await api.errors()
      errorMap.value = (res.data ?? {}) as Record<string, string>
    } catch {
      // 拉不到表不阻断流程：errorText 会兜底显示原始 code
    }
  }

  /** 错误码 → 中文文案；表里没有就原样返回 code，绝不自己编文案 */
  function errorText(code: string): string {
    return errorMap.value[code] ?? code
  }

  return {
    schema,
    config,
    loading,
    error,
    fields,
    hasSchema,
    loadSchema,
    initFromSchema,
    initFromConfig,
    getValue,
    setValue,
    reset,
    toPayload,
    errorMap,
    loadErrors,
    errorText,
  }
})
