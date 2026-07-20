import { describe, expect, it } from 'vitest'
import {
  REPLY_ARCHIVE_KEY,
  TITLE_ARCHIVE_KEY,
  TOOL_ARCHIVE_LIMIT,
  addToolArchiveEntry,
  buildInputSummary,
  createToolArchiveEntry,
  isValidReplyPayload,
  isValidRewritePayload,
  isValidScriptPayload,
  isValidTitlePayload,
  loadToolArchive,
  parseToolArchiveJson,
  saveToolArchive,
  type ReplyArchivePayload,
  type StorageLike,
  type TitleArchivePayload,
  type ToolArchiveEntry,
} from '../toolArchive'

const titlePayload: TitleArchivePayload = {
  topic: '打工人早八如何 10 分钟搞定营养早餐',
  platform: '小红书',
  style: '数字型',
  titles: [{ text: '10 分钟搞定早八营养餐', score: 88, elements: ['数字'] }],
}

const replyPayload: ReplyArchivePayload = {
  comments: ['博主用的是什么相机呀？'],
  tone: '热情',
  includePinned: true,
  replies: [{ comment: '博主用的是什么相机呀？', suggestions: ['回复1', '回复2'] }],
  pinnedComment: '欢迎关注！',
}

function makeEntry<P>(payload: P, overrides: Partial<ToolArchiveEntry<P>> = {}): ToolArchiveEntry<P> {
  return {
    id: 'tool_1',
    summary: '摘要',
    payload,
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

describe('buildInputSummary', () => {
  it('合并空白并截取前 50 字', () => {
    expect(buildInputSummary('  多行\n输入  文本 ')).toBe('多行 输入 文本')
    const long = '字'.repeat(80)
    expect(buildInputSummary(long)).toBe('字'.repeat(50) + '…')
  })
})

describe('payload 校验', () => {
  it('接受完整的各工具 payload', () => {
    expect(isValidTitlePayload(titlePayload)).toBe(true)
    expect(isValidReplyPayload(replyPayload)).toBe(true)
    expect(
      isValidRewritePayload({
        content: '原文',
        sourcePlatform: '',
        targetPlatforms: ['xiaohongshu'],
        results: [{ platform: 'xiaohongshu', title: '标题', content: '正文', tags: ['穿搭'] }],
      })
    ).toBe(true)
    expect(
      isValidScriptPayload({
        content: '主题',
        duration: '60s',
        scene: 'talking_head',
        script: {
          title: '片名', hook: '钩子', bgm_mood: '轻快', cta: '关注我',
          duration: '60s', scene: 'talking_head',
          segments: [{ time_range: '0-3s', visual: '画面', voiceover: '台词', subtitle_notes: '' }],
        },
      })
    ).toBe(true)
  })

  it('拒绝结果为空或字段缺失的 payload', () => {
    expect(isValidTitlePayload({ ...titlePayload, titles: [] })).toBe(false)
    expect(isValidTitlePayload({ ...titlePayload, topic: 1 })).toBe(false)
    expect(isValidReplyPayload({ ...replyPayload, replies: [] })).toBe(false)
    expect(isValidReplyPayload({ ...replyPayload, includePinned: 'yes' })).toBe(false)
    expect(isValidScriptPayload({ content: '主题', duration: '60s', scene: 'x', script: null })).toBe(false)
  })
})

describe('parseToolArchiveJson', () => {
  it('非法 JSON / 非数组返回空列表', () => {
    expect(parseToolArchiveJson('not-json', isValidTitlePayload)).toEqual([])
    expect(parseToolArchiveJson('{"a":1}', isValidTitlePayload)).toEqual([])
    expect(parseToolArchiveJson(null, isValidTitlePayload)).toEqual([])
  })

  it('损坏条目逐条丢弃并裁剪到上限', () => {
    const good = makeEntry(titlePayload)
    const broken = makeEntry({ ...titlePayload, titles: 'oops' }, { id: 'tool_2' })
    const list = parseToolArchiveJson(JSON.stringify([good, broken, { junk: true }]), isValidTitlePayload)
    expect(list).toHaveLength(1)
    expect(list[0].id).toBe('tool_1')

    const many = Array.from({ length: TOOL_ARCHIVE_LIMIT + 5 }, (_, i) =>
      makeEntry(titlePayload, { id: `tool_${i}` })
    )
    expect(parseToolArchiveJson(JSON.stringify(many), isValidTitlePayload)).toHaveLength(TOOL_ARCHIVE_LIMIT)
  })
})

describe('addToolArchiveEntry', () => {
  it('头插并裁剪到上限，不修改入参', () => {
    const list = [makeEntry(titlePayload, { id: 'old' })]
    const next = addToolArchiveEntry(list, makeEntry(titlePayload, { id: 'new' }), 2)
    expect(next.map(e => e.id)).toEqual(['new', 'old'])
    expect(list).toHaveLength(1)

    const capped = addToolArchiveEntry(next, makeEntry(titlePayload, { id: 'newer' }), 2)
    expect(capped.map(e => e.id)).toEqual(['newer', 'new'])
  })
})

describe('createToolArchiveEntry', () => {
  it('生成唯一 ID、摘要与时间戳', () => {
    const entry = createToolArchiveEntry({ input: titlePayload.topic, payload: titlePayload, now: 42 })
    expect(entry.id).toMatch(/^tool_42_/)
    expect(entry.summary).toBe(titlePayload.topic)
    expect(entry.createdAt).toBe(42)
    expect(entry.payload).toEqual(titlePayload)
  })
})

describe('loadToolArchive / saveToolArchive', () => {
  it('往返读写保持数据一致，且按工具键分桶', () => {
    const storage = memoryStorage()
    const titleList = [makeEntry(titlePayload)]
    const replyList = [makeEntry(replyPayload, { id: 'tool_r' })]

    saveToolArchive(TITLE_ARCHIVE_KEY, titleList, storage)
    saveToolArchive(REPLY_ARCHIVE_KEY, replyList, storage)

    expect(loadToolArchive(TITLE_ARCHIVE_KEY, isValidTitlePayload, storage)).toEqual(titleList)
    expect(loadToolArchive(REPLY_ARCHIVE_KEY, isValidReplyPayload, storage)).toEqual(replyList)
  })

  it('storage 不可用或数据损坏时返回空列表', () => {
    expect(loadToolArchive(TITLE_ARCHIVE_KEY, isValidTitlePayload, null)).toEqual([])
    const storage = memoryStorage({ [TITLE_ARCHIVE_KEY]: '{{broken' })
    expect(loadToolArchive(TITLE_ARCHIVE_KEY, isValidTitlePayload, storage)).toEqual([])
  })
})
