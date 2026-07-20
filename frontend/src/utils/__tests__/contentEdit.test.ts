import { describe, expect, it } from 'vitest'
import { addTag, normalizeTag, removeAt } from '../contentEdit'

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
