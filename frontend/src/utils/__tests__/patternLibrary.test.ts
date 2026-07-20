import { describe, expect, it } from 'vitest'
import {
  PATTERN_LIBRARY_KEY,
  PATTERN_LIBRARY_LIMIT,
  PATTERN_NAME_MAX_CHARS,
  addPatternEntry,
  createPatternEntry,
  isValidPatternEntry,
  loadPatternLibrary,
  normalizePatternName,
  parsePatternLibraryJson,
  removePatternEntry,
  savePatternLibrary,
  type PatternEntry,
  type StorageLike,
} from '../patternLibrary'

function makeEntry(overrides: Partial<PatternEntry> = {}): PatternEntry {
  return {
    id: 'pattern_1',
    name: '痛点清单体',
    template: '【痛点钩子】+【3 个避坑点】+【行动号召】',
    source_title: '新手化妆避坑指南',
    created_at: 1000,
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

describe('normalizePatternName', () => {
  it('合并空白并截断到上限', () => {
    expect(normalizePatternName('  痛点\n清单体 ')).toBe('痛点 清单体')
    const long = '名'.repeat(PATTERN_NAME_MAX_CHARS + 10)
    expect(normalizePatternName(long)).toBe('名'.repeat(PATTERN_NAME_MAX_CHARS) + '…')
  })

  it('空名回退到来源标题，再回退到「未命名套路」', () => {
    expect(normalizePatternName('', '对标标题')).toBe('对标标题')
    expect(normalizePatternName('  ', '  ')).toBe('未命名套路')
  })
})

describe('isValidPatternEntry', () => {
  it('接受完整条目', () => {
    expect(isValidPatternEntry(makeEntry())).toBe(true)
    // source_title 允许为空串（来源信息缺失不影响使用）
    expect(isValidPatternEntry(makeEntry({ source_title: '' }))).toBe(true)
  })

  it('拒绝字段缺失或类型错误的条目', () => {
    expect(isValidPatternEntry(null)).toBe(false)
    expect(isValidPatternEntry('junk')).toBe(false)
    expect(isValidPatternEntry(makeEntry({ id: '' }))).toBe(false)
    expect(isValidPatternEntry(makeEntry({ name: '' }))).toBe(false)
    expect(isValidPatternEntry(makeEntry({ template: '' }))).toBe(false)
    expect(isValidPatternEntry({ ...makeEntry(), template: 42 })).toBe(false)
    expect(isValidPatternEntry({ ...makeEntry(), source_title: undefined })).toBe(false)
    expect(isValidPatternEntry(makeEntry({ created_at: Number.NaN }))).toBe(false)
  })
})

describe('parsePatternLibraryJson', () => {
  it('非法 JSON / 非数组返回空列表', () => {
    expect(parsePatternLibraryJson(null)).toEqual([])
    expect(parsePatternLibraryJson('not-json')).toEqual([])
    expect(parsePatternLibraryJson('{"a":1}')).toEqual([])
  })

  it('损坏条目逐条丢弃并裁剪到上限', () => {
    const good = makeEntry()
    const broken = { ...makeEntry({ id: 'pattern_2' }), template: 42 }
    const list = parsePatternLibraryJson(JSON.stringify([good, broken, { junk: true }]))
    expect(list).toHaveLength(1)
    expect(list[0].id).toBe('pattern_1')

    const many = Array.from({ length: PATTERN_LIBRARY_LIMIT + 5 }, (_, i) =>
      makeEntry({ id: `pattern_${i}` })
    )
    expect(parsePatternLibraryJson(JSON.stringify(many))).toHaveLength(PATTERN_LIBRARY_LIMIT)
  })
})

describe('addPatternEntry / removePatternEntry', () => {
  it('头插并裁剪到上限，不修改入参', () => {
    const list = [makeEntry({ id: 'old' })]
    const next = addPatternEntry(list, makeEntry({ id: 'new' }), 2)
    expect(next.map(e => e.id)).toEqual(['new', 'old'])
    expect(list).toHaveLength(1)

    const capped = addPatternEntry(next, makeEntry({ id: 'newer' }), 2)
    expect(capped.map(e => e.id)).toEqual(['newer', 'new'])
  })

  it('按 ID 删除，不修改入参', () => {
    const list = [makeEntry({ id: 'a' }), makeEntry({ id: 'b' })]
    expect(removePatternEntry(list, 'a').map(e => e.id)).toEqual(['b'])
    expect(removePatternEntry(list, 'missing').map(e => e.id)).toEqual(['a', 'b'])
    expect(list).toHaveLength(2)
  })
})

describe('createPatternEntry', () => {
  it('生成唯一 ID 与时间戳，保留模板与来源', () => {
    const entry = createPatternEntry({
      name: '痛点清单体',
      template: '【钩子】+【正文】',
      sourceTitle: '对标标题',
      now: 42,
    })
    expect(entry.id).toMatch(/^pattern_42_/)
    expect(entry.name).toBe('痛点清单体')
    expect(entry.template).toBe('【钩子】+【正文】')
    expect(entry.source_title).toBe('对标标题')
    expect(entry.created_at).toBe(42)
  })

  it('名称留空时默认取对标标题', () => {
    const entry = createPatternEntry({ name: '  ', template: 't', sourceTitle: '对标标题', now: 1 })
    expect(entry.name).toBe('对标标题')
  })
})

describe('loadPatternLibrary / savePatternLibrary', () => {
  it('往返读写保持数据一致', () => {
    const storage = memoryStorage()
    const list = [makeEntry(), makeEntry({ id: 'pattern_2', name: '反差故事体' })]
    savePatternLibrary(list, storage)
    expect(loadPatternLibrary(storage)).toEqual(list)
    expect(storage.data[PATTERN_LIBRARY_KEY]).toBeTruthy()
  })

  it('写入时裁剪到上限', () => {
    const storage = memoryStorage()
    const many = Array.from({ length: PATTERN_LIBRARY_LIMIT + 3 }, (_, i) =>
      makeEntry({ id: `pattern_${i}` })
    )
    savePatternLibrary(many, storage)
    expect(loadPatternLibrary(storage)).toHaveLength(PATTERN_LIBRARY_LIMIT)
  })

  it('storage 不可用或数据损坏时返回空列表', () => {
    expect(loadPatternLibrary(null)).toEqual([])
    const storage = memoryStorage({ [PATTERN_LIBRARY_KEY]: '{{broken' })
    expect(loadPatternLibrary(storage)).toEqual([])
  })
})
