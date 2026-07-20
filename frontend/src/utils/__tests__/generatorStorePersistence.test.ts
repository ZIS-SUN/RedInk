/**
 * generator store 持久化的基础测试：
 * - localStorage shape 校验（脏数据整体丢弃）
 * - 版本迁移（版本不匹配丢弃并清理）
 * - saveToStorage 写入的 payload 结构
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGeneratorStore } from '../../stores/generator'

const STORAGE_KEY = 'generator-state'
const STORAGE_VERSION = 1

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

/** 写入待恢复的持久化数据后再创建 store（loadState 在 state() 初始化时执行） */
function seedAndCreateStore(payload: unknown) {
  storage.setItem(STORAGE_KEY, JSON.stringify(payload))
  return useGeneratorStore()
}

beforeEach(() => {
  storage = new LocalStorageMock()
  vi.stubGlobal('localStorage', storage)
  setActivePinia(createPinia())
})

describe('generator store 持久化恢复', () => {
  it('无持久化数据时使用默认初始状态', () => {
    const store = useGeneratorStore()
    expect(store.stage).toBe('input')
    expect(store.topic).toBe('')
    expect(store.taskId).toBeNull()
    expect(store.images).toEqual([])
  })

  it('版本匹配且 shape 合法时恢复关键字段', () => {
    const store = seedAndCreateStore({
      version: STORAGE_VERSION,
      stage: 'outline',
      topic: '秋冬穿搭',
      taskId: 'task_abc12345',
      stylePrompt: '胶片质感',
      outline: { raw: '第一页', pages: [{ index: 0, type: 'cover', content: '第一页' }] },
      progress: { current: 0, total: 1, status: 'idle' }
    })

    expect(store.stage).toBe('outline')
    expect(store.topic).toBe('秋冬穿搭')
    expect(store.taskId).toBe('task_abc12345')
    expect(store.stylePrompt).toBe('胶片质感')
    expect(store.outline.pages).toHaveLength(1)
  })

  it('版本不匹配（含旧版无 version 字段）时整体丢弃并清理 localStorage', () => {
    const store = seedAndCreateStore({
      stage: 'result',
      topic: '旧版数据'
    })

    expect(store.stage).toBe('input')
    expect(store.topic).toBe('')
    // 不合法数据已被清理
    expect(storage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('未来版本号同样丢弃，避免新结构数据污染旧代码', () => {
    const store = seedAndCreateStore({
      version: STORAGE_VERSION + 1,
      topic: '来自未来'
    })

    expect(store.topic).toBe('')
    expect(storage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('shape 非法（stage 为未知值）时整体丢弃', () => {
    const store = seedAndCreateStore({
      version: STORAGE_VERSION,
      stage: 'hacked',
      topic: '脏数据'
    })

    expect(store.stage).toBe('input')
    expect(store.topic).toBe('')
    expect(storage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('shape 非法（progress 字段类型错误）时整体丢弃', () => {
    const store = seedAndCreateStore({
      version: STORAGE_VERSION,
      topic: '主题',
      progress: { current: '0', total: 1, status: 'idle' }
    })

    expect(store.topic).toBe('')
    expect(storage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('JSON 损坏时回退默认状态且不抛错', () => {
    storage.setItem(STORAGE_KEY, '{not-json')
    const store = useGeneratorStore()
    expect(store.stage).toBe('input')
    expect(store.topic).toBe('')
  })
})

describe('generator store 持久化写入', () => {
  it('saveToStorage 写入带当前版本号的 payload，且不包含 userImages', () => {
    const store = useGeneratorStore()
    store.setTopic('测试主题')
    store.setStylePrompt('清新插画')
    store.saveToStorage()

    const raw = storage.getItem(STORAGE_KEY)
    expect(raw).not.toBeNull()

    const saved = JSON.parse(raw!)
    expect(saved.version).toBe(STORAGE_VERSION)
    expect(saved.topic).toBe('测试主题')
    expect(saved.stylePrompt).toBe('清新插画')
    // File 对象无法序列化，不应写入
    expect('userImages' in saved).toBe(false)
  })

  it('写入的数据能被新的 store 实例按原样恢复（round-trip）', () => {
    const store = useGeneratorStore()
    store.setTopic('往返测试')
    store.setTaskId('task_deadbeef')
    store.saveToStorage()

    // 新的 pinia 实例模拟页面刷新
    setActivePinia(createPinia())
    const restored = useGeneratorStore()

    expect(restored.topic).toBe('往返测试')
    expect(restored.taskId).toBe('task_deadbeef')
  })
})
