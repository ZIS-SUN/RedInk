/**
 * 大纲编辑标记（outlineDirty）测试：
 * - 编辑大纲的各个动作（改文/增删页/排序）置 dirty
 * - startGeneration 开始新一轮生成时清除 dirty
 * - dirty 随 localStorage 持久化并可恢复（刷新页面后仍能跳过旧图恢复）
 *
 * 该标记用于修复"大纲编辑后重新生成静默返回旧图"：
 * 生成页见到 dirty 时跳过 restoreFromHistory，走全新生成。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useGeneratorStore } from '../generator'
import type { Page } from '../../api/types'

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

function makePages(): Page[] {
  return [
    { index: 0, type: 'cover', content: '封面文案' },
    { index: 1, type: 'content', content: '内容文案' }
  ]
}

/** 构造"上一轮生成已全部完成"的 store，模拟用户回到大纲页时的状态 */
function createStoreAfterFinishedGeneration() {
  const store = useGeneratorStore()
  store.setTopic('测试主题')
  store.setOutline('封面文案\n\n<page>\n\n内容文案', makePages())
  store.startGeneration()
  store.updateProgress(0, 'done', 'http://img/0.png')
  store.updateProgress(1, 'done', 'http://img/1.png')
  store.finishGeneration('task_old00001')
  return store
}

beforeEach(() => {
  storage = new LocalStorageMock()
  vi.stubGlobal('localStorage', storage)
  setActivePinia(createPinia())
})

describe('outlineDirty 置位：生成完成后编辑大纲', () => {
  it('初始状态与生成完成后 dirty 均为 false', () => {
    const store = createStoreAfterFinishedGeneration()
    expect(store.outlineDirty).toBe(false)
  })

  it('修改某页文字后置 dirty', () => {
    const store = createStoreAfterFinishedGeneration()
    store.updatePage(1, '修改后的内容文案')
    expect(store.outlineDirty).toBe(true)
  })

  it('删除页面后置 dirty', () => {
    const store = createStoreAfterFinishedGeneration()
    store.deletePage(1)
    expect(store.outlineDirty).toBe(true)
  })

  it('新增页面后置 dirty', () => {
    const store = createStoreAfterFinishedGeneration()
    store.addPage('content', '新页面')
    expect(store.outlineDirty).toBe(true)
  })

  it('插入页面后置 dirty', () => {
    const store = createStoreAfterFinishedGeneration()
    store.insertPage(0, 'content', '插入页面')
    expect(store.outlineDirty).toBe(true)
  })

  it('拖拽排序后置 dirty', () => {
    const store = createStoreAfterFinishedGeneration()
    store.movePage(0, 1)
    expect(store.outlineDirty).toBe(true)
  })

  it('updatePage 索引不存在时不置 dirty', () => {
    const store = createStoreAfterFinishedGeneration()
    store.updatePage(99, '不存在的页面')
    expect(store.outlineDirty).toBe(false)
  })
})

describe('outlineDirty 清除', () => {
  it('startGeneration 开始新一轮生成时清除 dirty（编辑已生效）', () => {
    const store = createStoreAfterFinishedGeneration()
    store.updatePage(0, '编辑后的封面')
    expect(store.outlineDirty).toBe(true)

    store.startGeneration()
    expect(store.outlineDirty).toBe(false)
  })

  it('setOutlineDirty(false) 显式清除（从历史打开新记录时防串档）', () => {
    const store = createStoreAfterFinishedGeneration()
    store.markOutlineDirty()
    store.setOutlineDirty(false)
    expect(store.outlineDirty).toBe(false)
  })

  it('reset 清除 dirty', () => {
    const store = createStoreAfterFinishedGeneration()
    store.updatePage(0, '编辑后的封面')
    store.reset()
    expect(store.outlineDirty).toBe(false)
  })
})

describe('outlineDirty 持久化（刷新页面场景）', () => {
  it('dirty 随 saveToStorage 落盘，新 store 实例恢复后仍为 true', () => {
    const store = createStoreAfterFinishedGeneration()
    store.updatePage(1, '刷新前的编辑')
    store.saveToStorage()

    // 新的 pinia 实例模拟页面刷新
    setActivePinia(createPinia())
    const restored = useGeneratorStore()
    expect(restored.outlineDirty).toBe(true)
  })

  it('未编辑时刷新恢复 dirty 为 false（保持"从历史恢复旧图"的原有行为）', () => {
    const store = createStoreAfterFinishedGeneration()
    store.saveToStorage()

    setActivePinia(createPinia())
    const restored = useGeneratorStore()
    expect(restored.outlineDirty).toBe(false)
    expect(restored.stage).toBe('result')
  })

  it('持久化数据中 outlineDirty 类型非法时整体丢弃', () => {
    storage.setItem(
      STORAGE_KEY,
      JSON.stringify({ version: 1, topic: '脏数据', outlineDirty: 'yes' })
    )
    const store = useGeneratorStore()
    expect(store.topic).toBe('')
    expect(store.outlineDirty).toBe(false)
    expect(storage.getItem(STORAGE_KEY)).toBeNull()
  })
})
