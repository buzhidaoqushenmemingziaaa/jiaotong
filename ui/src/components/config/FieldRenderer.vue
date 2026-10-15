<script setup lang="ts">
/**
 * 3.2 产出：FieldRenderer.vue —— 单字段渲染器
 *
 * 职责边界：
 *  - 输入一个 FieldDef + v-model，输出一个完整可用的表单项（label + tooltip + 控件 + 单位）
 *  - 控件种类完全由 resolveControl() 查表决定，组件内**不写任何字段名、不写校验逻辑**
 *  - 外层栅格/分组由 3.3 负责，本组件只关心"一个字段长什么样"
 */
import { computed, ref, watch } from 'vue'
import { QuestionFilled } from '@element-plus/icons-vue'
import {
  type FieldDef,
  resolveControl,
  numberPropsOf,
  docOf,
} from './fieldTypes'

const props = defineProps<{
  /** 字段定义（来自 describe_config） */
  field: FieldDef
  /** 当前值 */
  modelValue?: unknown
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: unknown): void
}>()

// ---------- 派生 ----------

/** 控件种类：editable=false → readonly；有 enum → select；否则查 TYPE_TO_CONTROL */
const kind = computed(() => resolveControl(props.field))
/** 字段说明（tooltip），doc/desc 两种命名由 docOf 统一 */
const help = computed(() => docOf(props.field))
const unit = computed(() => props.field.unit ?? '')
const readOnly = computed(() => props.field.editable === false)

/** 统一 v-model 代理（any 以适配各控件的 modelValue 签名） */
const value = computed<any>({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

/**
 * list[int]/list[float] 用文本框编辑。
 * 需要本地缓冲：用户敲 "1," 这种中间态 JSON.parse 会失败，
 * 若直接 v-model 会导致输入框回弹。所以只把「解析成功」的结果向上提交。
 */
const listText = ref('')
watch(
  () => props.modelValue,
  (v) => {
    listText.value = Array.isArray(v) ? JSON.stringify(v) : ''
  },
  { immediate: true },
)

function onListNumberInput(text: string) {
  listText.value = text
  try {
    const parsed = JSON.parse(text)
    if (Array.isArray(parsed)) emit('update:modelValue', parsed)
  } catch {
    // 输入中间态，暂不提交
  }
}

/** readonly 兜底显示：字符串原样，其他类型 JSON 化 */
const readOnlyText = computed(() => {
  const v = props.modelValue
  if (v === null || v === undefined) return ''
  return typeof v === 'string' ? v : JSON.stringify(v)
})

/** 控件元素 id，便于点击 label 聚焦 */
const inputId = computed(() => `fr-${props.field.key}`)
</script>

<template>
  <el-form-item :prop="field.key" class="fr-item">
    <template #label>
      <span class="fr-label">
        <span class="fr-label-text">{{ field.label }}</span>
        <el-tooltip v-if="help" :content="help" placement="top" :show-after="150">
          <el-icon class="fr-help"><QuestionFilled /></el-icon>
        </el-tooltip>
      </span>
    </template>

    <div class="fr-control">
      <!-- str -->
      <el-input
        v-if="kind === 'input'"
        :id="inputId"
        v-model="value"
        class="fr-grow"
        :disabled="readOnly"
        clearable
      />

      <!-- int / float -->
      <el-input-number
        v-else-if="kind === 'input-number'"
        :id="inputId"
        v-model="value"
        v-bind="numberPropsOf(field)"
        class="fr-grow"
        :disabled="readOnly"
      />

      <!-- bool -->
      <el-switch
        v-else-if="kind === 'switch'"
        v-model="value"
        :disabled="readOnly"
      />

      <!-- enum -->
      <el-select
        v-else-if="kind === 'select'"
        :id="inputId"
        v-model="value"
        class="fr-grow"
        :disabled="readOnly"
        clearable
        placeholder="请选择"
      >
        <el-option
          v-for="opt in field.enum ?? []"
          :key="String(opt)"
          :label="String(opt)"
          :value="opt"
        />
      </el-select>

      <!-- list[str]：标签式，回车即新增 -->
      <el-select
        v-else-if="kind === 'list-str'"
        :id="inputId"
        v-model="value"
        class="fr-grow"
        multiple
        filterable
        allow-create
        default-first-option
        :disabled="readOnly"
        placeholder="输入后回车添加"
      />

      <!-- list[int] / list[float]：JSON 文本框 -->
      <el-input
        v-else-if="kind === 'list-number'"
        :id="inputId"
        :model-value="listText"
        class="fr-grow"
        :disabled="readOnly"
        placeholder="JSON 数组，如 [1, 2, 3]"
        @update:model-value="onListNumberInput"
      />

      <!-- 兜底：editable=false 或未知 type 一律只读 -->
      <el-input v-else :id="inputId" :model-value="readOnlyText" class="fr-grow" disabled />

      <span v-if="unit" class="fr-unit">{{ unit }}</span>
    </div>
  </el-form-item>
</template>

<style scoped>
.fr-item {
  margin-bottom: 18px;
}

.fr-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.fr-help {
  color: #a8abb2;
  cursor: help;
  font-size: 14px;
}

.fr-help:hover {
  color: #409eff;
}

.fr-control {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

/* 输入类控件撑满剩余宽度；开关保持原尺寸 */
.fr-grow {
  flex: 1 1 auto;
  min-width: 0;
  width: 100%;
}

.fr-unit {
  flex: 0 0 auto;
  color: #909399;
  font-size: 13px;
  white-space: nowrap;
}
</style>
