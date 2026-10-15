<script setup lang="ts">
/**
 * 参数配置页 —— 3.4 接入 Pinia store
 *
 * 数据来源全部改为 useConfigStore：
 *  - schema / config 放在 store，切页回来不丢（3.2、3.3 时是组件内局部 ref）
 *  - 值以点分 key 读写，store 内部转成嵌套结构（提交给引擎的形态）
 *
 * 布局规则（3.3）不变：按 groups 渲染折叠面板，列表字段整行、标量两列。
 * 校验规则（3.5）：由 schema 的 required 自动生成，只做必填性；业务校验归引擎。
 * 校验提交（3.6）：本地必填通过后 POST /api/config/validate，错误码经 describe_errors() 查表渲染。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import type { FormInstance } from 'element-plus'
import { api } from '@/api'
import { useConfigStore } from '@/stores/config'
import { type FieldDef, buildRules } from '@/components/config/fieldTypes'
import FieldRenderer from '@/components/config/FieldRenderer.vue'

const store = useConfigStore()
const { schema, config, loading, error } = storeToRefs(store)

/** 展开的分组 id（纯布局状态，不属于配置数据，留在组件内） */
const activeGroups = ref<string[]>([])

// schema 就绪后默认全部展开
watch(
  schema,
  (s) => {
    activeGroups.value = s.groups.map((g) => g.id)
  },
  { immediate: true },
)

onMounted(() => {
  store.loadSchema()
  store.loadErrors()
})

/**
 * 栅格宽度（24 栅格制）：列表类字段（车站列表、配属数组等）信息量大，占整行；
 * 标量字段两列并排，面板不至于过高。
 *
 * 用固定 :span 而非 :md 响应式断点——MVP 口径不做响应式（00_先读C.md §6），
 * 且断点在窄窗口下会静默退回整行，让"并排"设计失效。
 */
function spanOf(field: FieldDef): number {
  return field.type.startsWith('list[') ? 24 : 12
}

/** 总字段数，用于顶部统计 */
const fieldCount = computed(() => store.fields.length)

// ---------- 3.5 / 3.6 校验 ----------

const formRef = ref<FormInstance>()
/** 规则由 schema 自动生成，只含必填性；业务规则归引擎的 validate.py */
const rules = computed(() => buildRules(store.fields))

/** 校验报告（3.6 起由引擎的 /api/config/validate 产出） */
const report = ref<{
  ok: boolean
  summary: string
  items: Array<{ label: string; code: string; text: string }>
} | null>(null)
const submitting = ref(false)

/** 错误项里的 field 是点分 key，用 schema 的 label 还原成人话 */
function labelOf(key: string): string {
  return store.fields.find((f) => f.key === key)?.label ?? key
}

/**
 * 校验配置。两关：① 本地必填（快速反馈，挡在提交前）→ ② 引擎判定（权威）。
 *
 * ★ 引擎回包里的 message 字段被弃用：按契约 §1.5，C 只做 code → 文案 的查表渲染，
 *   说明文字一律取 describe_errors()，字段名取 schema 的 label。
 */
async function onValidate() {
  if (!formRef.value) return
  report.value = null

  try {
    await formRef.value.validate()
  } catch {
    report.value = {
      ok: false,
      summary: '存在未填写的必填项，请检查标红字段',
      items: [],
    }
    return
  }

  submitting.value = true
  try {
    // 先确保错误码表就绪，否则 errorText 会退化成原始 code（首次进页面时表可能还在路上）
    await store.loadErrors()

    const res = await api.validate({ config: store.toPayload() })
    const data = (res.data ?? {}) as {
      pass?: boolean
      items?: Array<{ field?: string; code?: string }>
    }
    const items = (data.items ?? []).map((it) => {
      const code = it.code ?? ''
      return { label: labelOf(it.field ?? ''), code, text: store.errorText(code) }
    })
    const pass = !!data.pass && items.length === 0
    report.value = {
      ok: pass,
      summary: pass ? '引擎校验通过' : `引擎校验未通过，共 ${items.length} 项`,
      items,
    }
  } catch (e: unknown) {
    report.value = {
      ok: false,
      summary: e instanceof Error ? `提交校验失败：${e.message}` : '提交校验失败',
      items: [],
    }
  } finally {
    submitting.value = false
  }
}

function onReset() {
  store.reset()
  report.value = null
  formRef.value?.clearValidate()
}
</script>

<template>
  <div v-loading="loading" class="config-view">
    <el-alert v-if="error" type="error" :closable="false" show-icon :title="error" />

    <el-alert
      v-else-if="!loading && fieldCount > 0"
      type="info"
      :closable="false"
      show-icon
      :title="`共 ${schema.groups.length} 组、${fieldCount} 个字段，均由后端 describe_config() 动态生成`"
    />

    <el-form
      ref="formRef"
      :model="config"
      :rules="rules"
      label-position="top"
      class="cfg-form"
    >
      <el-collapse v-model="activeGroups" class="cfg-collapse">
        <el-collapse-item v-for="g in schema.groups" :key="g.id" :name="g.id">
          <template #title>
            <span class="group-title">{{ g.title }}</span>
            <span class="group-count">{{ g.fields.length }} 项</span>
          </template>

          <el-row :gutter="20">
            <el-col v-for="f in g.fields" :key="f.key" :span="spanOf(f)">
              <FieldRenderer
                :field="f"
                :model-value="store.getValue(f.key)"
                @update:model-value="(v: unknown) => store.setValue(f.key, v)"
              />
            </el-col>
          </el-row>
        </el-collapse-item>
      </el-collapse>

      <el-empty
        v-if="!loading && schema.groups.length === 0"
        description="schema 为空"
      />
    </el-form>

    <div class="cfg-actions">
      <el-button type="primary" :loading="submitting" @click="onValidate">
        校验配置
      </el-button>
      <el-button @click="onReset">恢复默认值</el-button>
    </div>

    <el-alert
      v-if="report"
      :type="report.ok ? 'success' : 'error'"
      :closable="false"
      show-icon
      :title="report.summary"
    />

    <el-table
      v-if="report && report.items.length"
      :data="report.items"
      size="small"
      border
    >
      <el-table-column prop="label" label="字段" min-width="140" />
      <el-table-column prop="code" label="错误码" min-width="170" />
      <el-table-column prop="text" label="说明" min-width="200" />
    </el-table>

  </div>
</template>

<style scoped>
.config-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 200px;
}

.cfg-form {
  background: #fff;
  border-radius: 6px;
  padding: 4px 16px 8px;
}

.group-title {
  font-weight: 600;
  color: #303133;
}

.group-count {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}

.cfg-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
