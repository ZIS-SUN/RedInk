import { describe, expect, it } from 'vitest'
import {
  BENCHMARK_HISTORY_KEY,
  BENCHMARK_HISTORY_LIMIT,
  addEntry,
  buildSummary,
  createEntry,
  isValidEntry,
  loadHistory,
  parseHistoryJson,
  saveHistory,
  type BenchmarkHistoryEntry,
  type StorageLike,
} from '../benchmarkHistory'
import type { BenchmarkAnalysis } from '../../api/benchmark'

const analysis: BenchmarkAnalysis = {
  hook: '悬念钩子',
  opening: '开头制造反差',
  structure: ['抛出问题', '给出方法'],
  emotion: '焦虑缓解',
  audience: '新手创作者',
  viral_elements: ['数字标题'],
  reusable_template: '【痛点】+【方法】',
}

function makeEntry(overrides: Partial<BenchmarkHistoryEntry> = {}): BenchmarkHistoryEntry {
  return {
    id: 'bm_1',
    summary: '摘要',
    analysis,
    draft: '',
    myTopic: '',
    createdAt: 1000,
    ...overrides,
  }
}

/** 内存版 StorageLike，用于测试 load/save */
function memoryStorage(initial: Record<string, string> = {}): StorageLike & { data: Record<string, string> } {
  const data = { ...initial }
  return {
    data,
    getItem: (key: string) => (key in data ? data[key]! : null),
    setItem: (key: string, value: string) => {
      data[key] = value
    },
  }
}

describe('buildSummary', () => {
  it('短内容原样返回并合并空白', () => {
    expect(buildSummary('  第一行\n第二行  ')).toBe('第一行 第二行')
  })

  it('超过 50 字截断并加省略号', () => {
    const long = '字'.repeat(80)
    const summary = buildSummary(long)
    expect(summary).toBe('字'.repeat(50) + '…')
  })
})

describe('addEntry 上限裁剪', () => {
  it('新记录插到最前面', () => {
    const list = [makeEntry({ id: 'old' })]
    const next = addEntry(list, makeEntry({ id: 'new' }))
    expect(next.map(e => e.id)).toEqual(['new', 'old'])
    // 不修改入参
    expect(list).toHaveLength(1)
  })

  it('超过上限时裁掉最旧的', () => {
    let list: BenchmarkHistoryEntry[] = []
    for (let i = 0; i < BENCHMARK_HISTORY_LIMIT + 5; i++) {
      list = addEntry(list, makeEntry({ id: `bm_${i}` }))
    }
    expect(list).toHaveLength(BENCHMARK_HISTORY_LIMIT)
    expect(list[0]!.id).toBe(`bm_${BENCHMARK_HISTORY_LIMIT + 4}`)
    // 最早的几条被裁掉
    expect(list.some(e => e.id === 'bm_0')).toBe(false)
  })
})

describe('parseHistoryJson 损坏数据丢弃', () => {
  it('null / 空串返回空列表', () => {
    expect(parseHistoryJson(null)).toEqual([])
    expect(parseHistoryJson('')).toEqual([])
  })

  it('非法 JSON 返回空列表', () => {
    expect(parseHistoryJson('{oops')).toEqual([])
  })

  it('非数组返回空列表', () => {
    expect(parseHistoryJson('{"a":1}')).toEqual([])
  })

  it('数组中损坏条目被逐条丢弃，完好条目保留', () => {
    const good = makeEntry({ id: 'good' })
    const json = JSON.stringify([
      good,
      { id: 'no-analysis', summary: 's', draft: '', myTopic: '', createdAt: 1 },
      'not-an-object',
      null,
      { ...good, id: '' },
      { ...good, createdAt: 'yesterday' },
      { ...good, analysis: { ...analysis, structure: '不是数组' } },
    ])
    const result = parseHistoryJson(json)
    expect(result.map(e => e.id)).toEqual(['good'])
  })

  it('超过上限的持久化数据读入时也会被裁剪', () => {
    const entries = Array.from({ length: 30 }, (_, i) => makeEntry({ id: `bm_${i}` }))
    const result = parseHistoryJson(JSON.stringify(entries))
    expect(result).toHaveLength(BENCHMARK_HISTORY_LIMIT)
  })
})

describe('isValidEntry', () => {
  it('完整条目通过校验', () => {
    expect(isValidEntry(makeEntry())).toBe(true)
  })

  it('缺字段不通过', () => {
    const { draft: _draft, ...rest } = makeEntry()
    expect(isValidEntry(rest)).toBe(false)
  })
})

describe('createEntry', () => {
  it('生成摘要、时间戳与唯一 id', () => {
    const entry = createEntry({
      input: '一篇很长的对标内容'.repeat(20),
      analysis,
      draft: '草稿',
      myTopic: '我的主题',
      now: 12345,
    })
    expect(entry.createdAt).toBe(12345)
    expect(entry.summary.length).toBeLessThanOrEqual(51)
    expect(entry.draft).toBe('草稿')
    expect(entry.myTopic).toBe('我的主题')
    expect(entry.id).toMatch(/^bm_12345_/)
    expect(isValidEntry(entry)).toBe(true)
  })
})

describe('loadHistory / saveHistory', () => {
  it('往返读写一致', () => {
    const storage = memoryStorage()
    const list = [makeEntry({ id: 'a' }), makeEntry({ id: 'b' })]
    saveHistory(list, storage)
    expect(loadHistory(storage).map(e => e.id)).toEqual(['a', 'b'])
  })

  it('存储中是损坏数据时读取返回空列表', () => {
    const storage = memoryStorage({ [BENCHMARK_HISTORY_KEY]: '###broken###' })
    expect(loadHistory(storage)).toEqual([])
  })

  it('storage 不可用时安全降级', () => {
    expect(loadHistory(null)).toEqual([])
    expect(() => saveHistory([makeEntry()], null)).not.toThrow()
  })

  it('保存时按上限裁剪', () => {
    const storage = memoryStorage()
    const list = Array.from({ length: 30 }, (_, i) => makeEntry({ id: `bm_${i}` }))
    saveHistory(list, storage)
    expect(loadHistory(storage)).toHaveLength(BENCHMARK_HISTORY_LIMIT)
  })
})
