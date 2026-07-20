/**
 * 结果页内容编辑（标题/文案/标签）相关的纯逻辑
 * 不依赖 store / DOM，便于单测覆盖
 */

/**
 * 规范化单个标签：
 * - 去掉首尾空白
 * - 去掉开头的 #（含全角 ＃、可重复出现）以及 # 与文字之间的空白
 */
export function normalizeTag(input: string): string {
  return input.trim().replace(/^[#＃\s]+/, '').trim()
}

/**
 * 向标签列表末尾添加新标签（先规范化，再去重）
 * @returns 新数组；输入无效（规范化后为空）或已存在时原样返回原数组
 */
export function addTag(tags: string[], input: string): string[] {
  const tag = normalizeTag(input)
  if (!tag || tags.includes(tag)) return tags
  return [...tags, tag]
}

/**
 * 移除列表中指定索引的元素
 * @returns 新数组；索引越界时原样返回原数组
 */
export function removeAt<T>(list: T[], index: number): T[] {
  if (index < 0 || index >= list.length) return list
  return list.filter((_, i) => i !== index)
}

/** 编辑留痕来源：manual-用户手改，polish-AI 润色后应用 */
export type EditTraceSource = 'manual' | 'polish'

/**
 * 单条编辑留痕（「AI 原文 → 用户终稿」的 diff 记录）
 * 与后端 PUT /api/history/:id 的 edit_trace 参数同构，edited_at 由后端补
 */
export interface EditTrace {
  page_index: number
  original_text: string
  edited_text: string
  source: EditTraceSource
}

/**
 * 构建编辑留痕：原文与新文相同（无 diff 价值）或索引非法时返回 null，
 * 调用方据此跳过上报
 */
export function buildEditTrace(
  pageIndex: number,
  originalText: string,
  editedText: string,
  source: EditTraceSource = 'manual'
): EditTrace | null {
  if (!Number.isInteger(pageIndex) || pageIndex < 0) return null
  if (originalText === editedText) return null
  return {
    page_index: pageIndex,
    original_text: originalText,
    edited_text: editedText,
    source
  }
}

/**
 * 五星评分的点击语义：点已选中的星 = 清除评分，点其他星 = 改为该分值
 */
export function resolveNextRating(current: number | null, clicked: number): number | null {
  return clicked === current ? null : clicked
}
