/**
 * 目标搜索词（seoKeywords，小红书搜索埋词）store 测试：
 * - setSeoKeywords 归一化：去空白、去空项、去重、最多保留 3 个
 * - 随 localStorage 持久化并可恢复
 * - 向后兼容：旧版持久化数据没有 seoKeywords 字段时正常加载为空数组
 * - 类型非法时整体丢弃持久化数据（与其他字段的防护策略一致）
 * - reset 清空搜索词
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGeneratorStore } from '../generator'

const STORAGE_KEY = 'generator-state'

/** 内存版 localStorage（node 环境没有原生实现） */
class LocalStorageMock {
  private data = new Map<string, string>()

  getItem(key: string): string | null {
    return this.data.has(key) ? this.data.get(key)! : null
  }

  setItem(key: string, value: string) {
    this.data.set(key, String(value))
  }

  removeItem(key: string) {
    this.data.delete(key)
  }

  clear() {
    this.data.clear()
  }
}

let storage: LocalStorageMock

beforeEach(() => {
  storage = new LocalStorageMock()
  vi.stubGlobal('localStorage', storage)
  setActivePinia(createPinia())
})

describe('setSeoKeywords 归一化', () => {
  it('初始状态为空数组', () => {
    const store = useGeneratorStore()
    expect(store.seoKeywords).toEqual([])
  })

  it('正常写入 1-3 个词', () => {
    const store = useGeneratorStore()
    store.setSeoKeywords(['秋冬穿搭', '显瘦穿搭'])
    expect(store.seoKeywords).toEqual(['秋冬穿搭', '显瘦穿搭'])
  })

  it('去首尾空白并过滤空项', () => {
    const store = useGeneratorStore()
    store.setSeoKeywords(['  秋冬穿搭 ', '', '   '])
    expect(store.seoKeywords).toEqual(['秋冬穿搭'])
  })

  it('去重且最多保留前 3 个', () => {
    const store = useGeneratorStore()
    store.setSeoKeywords(['一', '二', '一', '三', '四'])
    expect(store.seoKeywords).toEqual(['一', '二', '三'])
  })

  it('传空数组可清空', () => {
    const store = useGeneratorStore()
    store.setSeoKeywords(['秋冬穿搭'])
    store.setSeoKeywords([])
    expect(store.seoKeywords).toEqual([])
  })
})

describe('持久化与恢复', () => {
  it('seoKeywords 随 saveToStorage 落盘，新 store 实例可恢复', () => {
    const store = useGeneratorStore()
    store.setSeoKeywords(['秋冬穿搭', '显瘦穿搭'])
    store.saveToStorage()

    // 新的 pinia 实例模拟页面刷新
    setActivePinia(createPinia())
    const restored = useGeneratorStore()
    expect(restored.seoKeywords).toEqual(['秋冬穿搭', '显瘦穿搭'])
  })

  it('向后兼容：旧版持久化数据没有 seoKeywords 字段时加载为空数组且不丢弃其他数据', () => {
    // 模拟本次改动之前落盘的数据（version 1，无 seoKeywords 键）
    storage.setItem(
      STORAGE_KEY,
      JSON.stringify({ version: 1, topic: '旧数据主题', brandId: 'brand-1' })
    )

    const store = useGeneratorStore()
    expect(store.topic).toBe('旧数据主题')
    expect(store.brandId).toBe('brand-1')
    expect(store.seoKeywords).toEqual([])
  })

  it('seoKeywords 类型非法（非数组）时整体丢弃持久化数据', () => {
    storage.setItem(
      STORAGE_KEY,
      JSON.stringify({ version: 1, topic: '脏数据', seoKeywords: '不是数组' })
    )

    const store = useGeneratorStore()
    expect(store.topic).toBe('')
    expect(store.seoKeywords).toEqual([])
    expect(storage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('数组内的非字符串项在恢复时被过滤', () => {
    storage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        version: 1,
        topic: '主题',
        seoKeywords: ['秋冬穿搭', 123, null, '显瘦穿搭']
      })
    )

    const store = useGeneratorStore()
    expect(store.topic).toBe('主题')
    expect(store.seoKeywords).toEqual(['秋冬穿搭', '显瘦穿搭'])
  })
})

describe('reset', () => {
  it('reset 清空 seoKeywords 并清除持久化数据', () => {
    const store = useGeneratorStore()
    store.setSeoKeywords(['秋冬穿搭'])
    store.saveToStorage()

    store.reset()
    expect(store.seoKeywords).toEqual([])
    expect(storage.getItem(STORAGE_KEY)).toBeNull()
  })
})
