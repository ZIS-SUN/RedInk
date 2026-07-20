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
