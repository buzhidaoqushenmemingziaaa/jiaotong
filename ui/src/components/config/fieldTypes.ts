/**
 * 3.1 产出：schema 类型 → Element Plus 控件 映射表
 *
 * 契约来源：
 *  - 02_设计文档/...接口契约.md §1.4   describe_config() 返回结构
 *  - 02_设计文档/系统设计稿.md §5.1    字段形状 {key, label, type, unit, required, default, enum?, range?, desc}
 *  - 01_数据契约/示例_describe_config.json
 *
 * 设计原则（契约 §1.5）：
 *  - C 不手抄字段名、不自己写校验文案、不编中文文案
 *  - C 只做 "type → 控件" 的查表渲染，未知 type 一律只读兜底
 */

// ---------- 字段定义（与后端 describe_config 对齐） ----------

/** 契约中出现的 type 字符串字面量（mock 已见 list[str]/int，其余按契约与设计稿推断） */
export type FieldType =
  | 'str'
  | 'int'
  | 'float'
  | 'bool'
  | 'enum'
  | 'list[str]'
  | 'list[int]'
  | 'list[float]'
  | (string & {}) // 允许未知 type 通过类型检查，运行时走 readonly 兜底

export interface FieldRange {
  min?: number
  max?: number
  step?: number
}

export interface FieldDef {
  /** 点分嵌套路径，如 "line.stations" / "scenario.horizon_steps" */
  key: string
  /** 中文标签（B 提供，C 不改） */
  label: string
  type: FieldType
  /** 单位后缀，如 "km" / "min"，渲染在控件右侧 */
  unit?: string
  required?: boolean
  /** 默认值（初始化 formData 用） */
  default?: unknown
  /** 枚举取值（type=enum 时必有） */
  enum?: Array<string | number>
  /** 数值范围（type=int/float 时可选） */
  range?: FieldRange
  /** editable:false 时只读（如派生字段 line.total_length_km） */
  editable?: boolean
  /** 字段说明（hover tooltip）。契约用 doc，设计稿用 desc，两者兼容 */
  doc?: string
  desc?: string
}

export interface GroupDef {
  id: string
  title: string
  fields: FieldDef[]
}

export interface ConfigSchema {
  groups: GroupDef[]
}

// ---------- 控件种类（FieldRenderer 渲染分支） ----------

export type ControlKind =
  | 'input'         // el-input            单行文本
  | 'input-number'  // el-input-number     数值（int/float）
  | 'switch'        // el-switch           布尔
  | 'select'        // el-select           枚举单选
  | 'list-str'      // tag 编辑器           list[str]，允许新增/删除
  | 'list-number'   // JSON 文本框          list[int]/list[float]，MVP 先用文本框+解析
  | 'readonly'      // 只读文本             editable:false 或未知 type

// ---------- 核心映射表（3.1 的核心产出） ----------

/**
 * type → 控件 的查表。
 *
 * 优先级（在 resolveControl 里体现）：
 *   1. editable === false           → readonly
 *   2. type === 'enum' 或带 enum    → select
 *   3. 按下表查 type                 → 对应控件
 *   4. 表里没有                     → readonly（兜底，绝不让表单崩）
 */
export const TYPE_TO_CONTROL: Record<string, ControlKind> = {
  str: 'input',
  int: 'input-number',
  float: 'input-number',
  bool: 'switch',
  enum: 'select',
  'list[str]': 'list-str',
  'list[int]': 'list-number',
  'list[float]': 'list-number',
}

/** 根据字段定义解析最终控件 */
export function resolveControl(field: FieldDef): ControlKind {
  if (field.editable === false) return 'readonly'
  if (field.type === 'enum' || (field.enum && field.enum.length > 0)) return 'select'
  return TYPE_TO_CONTROL[field.type] ?? 'readonly'
}

// ---------- 各 type 的空值（3.4 初始化 formData 用） ----------

export function emptyValueOf(type: FieldType): unknown {
  switch (type) {
    case 'str': return ''
    case 'int':
    case 'float': return null
    case 'bool': return false
    case 'enum': return null
    case 'list[str]':
    case 'list[int]':
    case 'list[float]': return []
    default: return null
  }
}

/** 字段初始值：优先 default，其次空值 */
export function initialValueOf(field: FieldDef): unknown {
  return field.default !== undefined ? field.default : emptyValueOf(field.type)
}

// ---------- 控件 props 辅助（3.2 FieldRenderer 用） ----------

/** el-input-number 的 props：从 range 拿 min/max/step；int 强制 precision=0 */
export function numberPropsOf(field: FieldDef) {
  const { min, max, step } = field.range ?? {}
  return {
    min,
    max,
    step: step ?? (field.type === 'int' ? 1 : 0.1),
    precision: field.type === 'int' ? 0 : undefined,
    controlsPosition: 'right' as const,
  }
}

/** 字段说明文案（兼容 doc/desc 两种命名） */
export function docOf(field: FieldDef): string {
  return field.doc ?? field.desc ?? ''
}
