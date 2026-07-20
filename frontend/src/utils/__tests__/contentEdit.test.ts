import { describe, expect, it } from 'vitest'
import {
  addTag,
  buildEditTrace,
  normalizeTag,
  removeAt,
  resolveNextRating
} from '../contentEdit'

describe('normalizeTag', () => {
  it('去掉首尾空白', () => {
    expect(normalizeTag('  美食  ')).toBe('美食')
  })

  it('去掉开头的 # 号', () => {
    expect(normalizeTag('#美食')).toBe('美食')
  })

  it('去掉多个 # 与全角 ＃', () => {
    expect(normalizeTag('##美食')).toBe('美食')
    expect(normalizeTag('＃美食')).toBe('美食')
  })

  it('去掉 # 与文字之间的空白', () => {
    expect(normalizeTag('# 美食 探店')).toBe('美食 探店')
  })

  it('纯 # 或纯空白返回空字符串', () => {
    expect(normalizeTag('###')).toBe('')
    expect(normalizeTag('   ')).toBe('')
    expect(normalizeTag('')).toBe('')
  })
})

describe('addTag', () => {
  it('规范化后追加到末尾（返回新数组）', () => {
    const tags = ['美食']
    const result = addTag(tags, ' #探店 ')
    expect(result).toEqual(['美食', '探店'])
    expect(result).not.toBe(tags)
  })

  it('重复标签不追加（原样返回原数组）', () => {
    const tags = ['美食', '探店']
    expect(addTag(tags, '#美食')).toBe(tags)
  })

  it('规范化后为空不追加', () => {
    const tags = ['美食']
    expect(addTag(tags, '  ## ')).toBe(tags)
  })

  it('不修改原数组', () => {
    const tags = ['美食']
    addTag(tags, '探店')
    expect(tags).toEqual(['美食'])
  })
})

describe('removeAt', () => {
  it('移除指定索引元素（返回新数组）', () => {
    const list = ['a', 'b', 'c']
    const result = removeAt(list, 1)
    expect(result).toEqual(['a', 'c'])
    expect(result).not.toBe(list)
  })

  it('索引越界时原样返回原数组', () => {
    const list = ['a']
    expect(removeAt(list, -1)).toBe(list)
    expect(removeAt(list, 1)).toBe(list)
  })

  it('不修改原数组', () => {
    const list = ['a', 'b']
    removeAt(list, 0)
    expect(list).toEqual(['a', 'b'])
  })
})

describe('buildEditTrace', () => {
  it('构建 manual 编辑留痕', () => {
    expect(buildEditTrace(2, 'AI 原文', '用户终稿')).toEqual({
      page_index: 2,
      original_text: 'AI 原文',
      edited_text: '用户终稿',
      source: 'manual'
    })
  })

  it('支持 polish 来源', () => {
    expect(buildEditTrace(0, '原文', '润色后', 'polish')?.source).toBe('polish')
  })

  it('原文与新文相同时返回 null（无 diff 价值）', () => {
    expect(buildEditTrace(0, '一样', '一样')).toBeNull()
  })

  it('索引非法时返回 null', () => {
    expect(buildEditTrace(-1, 'a', 'b')).toBeNull()
    expect(buildEditTrace(1.5, 'a', 'b')).toBeNull()
    expect(buildEditTrace(NaN, 'a', 'b')).toBeNull()
  })
})

describe('resolveNextRating', () => {
  it('点未选中的星改为该分值', () => {
    expect(resolveNextRating(null, 4)).toBe(4)
    expect(resolveNextRating(2, 5)).toBe(5)
  })

  it('点已选中的星清除评分', () => {
    expect(resolveNextRating(3, 3)).toBeNull()
  })
})
