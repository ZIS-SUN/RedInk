import { describe, expect, it } from 'vitest'
import {
  DEFAULT_PUBLISH_TIME,
  IDEA_ARCHIVE_LIMIT,
  INSIGHT_ARCHIVE_KEY,
  TOPIC_ARCHIVE_KEY,
  addArchiveEntry,
  buildCreationTopicFromPlan,
  createInsightArchiveEntry,
  createTopicArchiveEntry,
  ideaToPlanInput,
  isValidInsightEntry,
  isValidTopicEntry,
  loadInsightArchive,
  loadTopicArchive,
  parseInsightArchiveJson,
  parsePlanNotes,
  parseTopicArchiveJson,
  platformLabelToPlanPlatform,
  saveInsightArchive,
  saveTopicArchive,
  tomorrowDateStr,
  type InsightArchiveEntry,
  type StorageLike,
  type TopicArchiveEntry,
} from '../ideaArchive'
import type { TopicIdea } from '../../api/topic'
import type { PainPoint } from '../../api/insight'

const idea: TopicIdea = {
  title: '新手减脂的 5 个常见误区',
  angle: '反常识盘点，击中新手焦虑',
  format: '清单',
  heat: 88,
  tags: ['减脂', '新手健身'],
}

const painPoint: PainPoint = {
  theme: '不知道怎么选相机',
  summary: '新手预算有限，参数看不懂',
  frequency: 6,
  evidence: ['博主用的是什么相机呀？'],
  topics: [idea],
}

function makeTopicEntry(overrides: Partial<TopicArchiveEntry> = {}): TopicArchiveEntry {
  return {
    id: 'topic_1',
    niche: '健身减脂',
    platform: '小红书',
    accountContextUsed: false,
    topics: [idea],
    createdAt: 1000,
    ...overrides,
  }
}

function makeInsightEntry(overrides: Partial<InsightArchiveEntry> = {}): InsightArchiveEntry {
  return {
    id: 'insight_1',
    niche: '摄影教学',
    comments: ['博主用的是什么相机呀？', '为什么我拍得很丑'],
    commentCount: 2,
    painPoints: [painPoint],
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

describe('isValidTopicEntry', () => {
  it('完整条目通过校验', () => {
    expect(isValidTopicEntry(makeTopicEntry())).toBe(true)
  })

  it('缺字段 / 类型错误 / 空结果不通过', () => {
    const { platform: _platform, ...missing } = makeTopicEntry()
    expect(isValidTopicEntry(missing)).toBe(false)
    expect(isValidTopicEntry(makeTopicEntry({ createdAt: NaN }))).toBe(false)
    expect(isValidTopicEntry(makeTopicEntry({ topics: [] }))).toBe(false)
    expect(isValidTopicEntry(null)).toBe(false)
    expect(isValidTopicEntry('not-an-object')).toBe(false)
  })

  it('内部选题结构损坏不通过', () => {
    const broken = makeTopicEntry({
      topics: [{ ...idea, tags: '不是数组' } as unknown as TopicIdea],
    })
    expect(isValidTopicEntry(broken)).toBe(false)
  })
})

describe('isValidInsightEntry', () => {
  it('完整条目通过校验', () => {
    expect(isValidInsightEntry(makeInsightEntry())).toBe(true)
  })

  it('缺字段 / 空结果 / 痛点结构损坏不通过', () => {
    const { comments: _comments, ...missing } = makeInsightEntry()
    expect(isValidInsightEntry(missing)).toBe(false)
    expect(isValidInsightEntry(makeInsightEntry({ painPoints: [] }))).toBe(false)
    const brokenPoint = { ...painPoint, evidence: [123] } as unknown as PainPoint
    expect(isValidInsightEntry(makeInsightEntry({ painPoints: [brokenPoint] }))).toBe(false)
  })
})

describe('parseTopicArchiveJson / parseInsightArchiveJson 损坏数据丢弃', () => {
  it('null / 空串 / 非法 JSON / 非数组返回空列表', () => {
    expect(parseTopicArchiveJson(null)).toEqual([])
    expect(parseTopicArchiveJson('')).toEqual([])
    expect(parseTopicArchiveJson('{oops')).toEqual([])
    expect(parseInsightArchiveJson('{"a":1}')).toEqual([])
  })

  it('数组中损坏条目被逐条丢弃，完好条目保留', () => {
    const good = makeTopicEntry({ id: 'good' })
    const json = JSON.stringify([
      good,
      { id: 'no-topics', niche: '', platform: '', accountContextUsed: false, createdAt: 1 },
      'not-an-object',
      null,
      { ...good, id: '' },
    ])
    expect(parseTopicArchiveJson(json).map(e => e.id)).toEqual(['good'])
  })

  it('超过上限的持久化数据读入时也会被裁剪', () => {
    const entries = Array.from({ length: 15 }, (_, i) => makeInsightEntry({ id: `insight_${i}` }))
    expect(parseInsightArchiveJson(JSON.stringify(entries))).toHaveLength(IDEA_ARCHIVE_LIMIT)
  })
})

describe('addArchiveEntry 上限裁剪', () => {
  it('新记录插到最前面且不修改入参', () => {
    const list = [makeTopicEntry({ id: 'old' })]
    const next = addArchiveEntry(list, makeTopicEntry({ id: 'new' }))
    expect(next.map(e => e.id)).toEqual(['new', 'old'])
    expect(list).toHaveLength(1)
  })

  it('超过上限（10）时裁掉最旧的', () => {
    let list: TopicArchiveEntry[] = []
    for (let i = 0; i < IDEA_ARCHIVE_LIMIT + 3; i++) {
      list = addArchiveEntry(list, makeTopicEntry({ id: `topic_${i}` }))
    }
    expect(list).toHaveLength(IDEA_ARCHIVE_LIMIT)
    expect(list[0]!.id).toBe(`topic_${IDEA_ARCHIVE_LIMIT + 2}`)
    expect(list.some(e => e.id === 'topic_0')).toBe(false)
  })
})

describe('createTopicArchiveEntry / createInsightArchiveEntry', () => {
  it('生成时间戳与唯一 id，且通过自身校验', () => {
    const entry = createTopicArchiveEntry({
      niche: '健身减脂',
      platform: '抖音',
      accountContextUsed: true,
      topics: [idea],
      now: 12345,
    })
    expect(entry.createdAt).toBe(12345)
    expect(entry.id).toMatch(/^topic_12345_/)
    expect(entry.accountContextUsed).toBe(true)
    expect(isValidTopicEntry(entry)).toBe(true)
  })

  it('洞察存档保留输入评论与结果', () => {
    const entry = createInsightArchiveEntry({
      niche: '',
      comments: ['评论 A'],
      commentCount: 1,
      painPoints: [painPoint],
      now: 500,
    })
    expect(entry.id).toMatch(/^insight_500_/)
    expect(entry.comments).toEqual(['评论 A'])
    expect(isValidInsightEntry(entry)).toBe(true)
  })
})

describe('load / save 往返', () => {
  it('两类存档各自读写一致、互不串键', () => {
    const storage = memoryStorage()
    saveTopicArchive([makeTopicEntry({ id: 'a' })], storage)
    saveInsightArchive([makeInsightEntry({ id: 'b' })], storage)
    expect(loadTopicArchive(storage).map(e => e.id)).toEqual(['a'])
    expect(loadInsightArchive(storage).map(e => e.id)).toEqual(['b'])
    expect(Object.keys(storage.data).sort()).toEqual([INSIGHT_ARCHIVE_KEY, TOPIC_ARCHIVE_KEY].sort())
  })

  it('存储中是损坏数据时读取返回空列表', () => {
    const storage = memoryStorage({ [TOPIC_ARCHIVE_KEY]: '###broken###' })
    expect(loadTopicArchive(storage)).toEqual([])
  })

  it('storage 不可用时安全降级', () => {
    expect(loadTopicArchive(null)).toEqual([])
    expect(loadInsightArchive(null)).toEqual([])
    expect(() => saveTopicArchive([makeTopicEntry()], null)).not.toThrow()
  })

  it('保存时按上限裁剪', () => {
    const storage = memoryStorage()
    const list = Array.from({ length: 15 }, (_, i) => makeTopicEntry({ id: `topic_${i}` }))
    saveTopicArchive(list, storage)
    expect(loadTopicArchive(storage)).toHaveLength(IDEA_ARCHIVE_LIMIT)
  })
})

describe('platformLabelToPlanPlatform', () => {
  it('已知平台中文名映射为枚举', () => {
    expect(platformLabelToPlanPlatform('小红书')).toBe('xiaohongshu')
    expect(platformLabelToPlanPlatform('抖音')).toBe('douyin')
    expect(platformLabelToPlanPlatform('公众号')).toBe('gongzhonghao')
    expect(platformLabelToPlanPlatform('B站')).toBe('bilibili')
    expect(platformLabelToPlanPlatform(' 视频号 ')).toBe('shipinhao')
  })

  it('未知平台返回 null', () => {
    expect(platformLabelToPlanPlatform('快手')).toBeNull()
    expect(platformLabelToPlanPlatform('')).toBeNull()
  })
})

describe('tomorrowDateStr', () => {
  it('返回次日日期（本地时区 YYYY-MM-DD）', () => {
    expect(tomorrowDateStr(new Date(2026, 6, 20))).toBe('2026-07-21')
  })

  it('月末 / 年末正确进位', () => {
    expect(tomorrowDateStr(new Date(2026, 6, 31))).toBe('2026-08-01')
    expect(tomorrowDateStr(new Date(2026, 11, 31))).toBe('2027-01-01')
  })
})

describe('ideaToPlanInput 选题→日历条目字段映射', () => {
  it('标题直取，备注带切入角度与建议标签，状态固定 idea', () => {
    const input = ideaToPlanInput(idea, {
      platform: 'xiaohongshu',
      publishDate: '2026-07-21',
      publishTime: '18:00',
    })
    expect(input).toEqual({
      title: '新手减脂的 5 个常见误区',
      platform: 'xiaohongshu',
      publish_date: '2026-07-21',
      publish_time: '18:00',
      status: 'idea',
      notes: '切入角度：反常识盘点，击中新手焦虑\n建议标签：#减脂 #新手健身',
    })
  })

  it('未提供发布时间时回退默认 19:00', () => {
    const input = ideaToPlanInput(idea, {
      platform: 'douyin',
      publishDate: '2026-07-21',
    })
    expect(input.publish_time).toBe(DEFAULT_PUBLISH_TIME)
    expect(DEFAULT_PUBLISH_TIME).toBe('19:00')
  })

  it('空角度 / 空标签跳过对应备注行', () => {
    const bare = ideaToPlanInput(
      { title: '标题', angle: '  ', tags: [] },
      { platform: 'bilibili', publishDate: '2026-07-21' }
    )
    expect(bare.notes).toBe('')

    const onlyTags = ideaToPlanInput(
      { title: '标题', angle: '', tags: ['标签'] },
      { platform: 'bilibili', publishDate: '2026-07-21' }
    )
    expect(onlyTags.notes).toBe('建议标签：#标签')
  })
})

describe('parsePlanNotes 日历备注解析（ideaToPlanInput 的逆向）', () => {
  it('解析出切入角度与建议标签（去掉 # 前缀）', () => {
    const notes = '切入角度：反常识盘点，击中新手焦虑\n建议标签：#减脂 #新手健身'
    expect(parsePlanNotes(notes)).toEqual({
      angle: '反常识盘点，击中新手焦虑',
      tags: ['减脂', '新手健身'],
    })
  })

  it('手写备注 / 空备注不匹配时返回空值', () => {
    expect(parsePlanNotes('记得带素材去公园拍')).toEqual({ angle: '', tags: [] })
    expect(parsePlanNotes('')).toEqual({ angle: '', tags: [] })
  })

  it('ideaToPlanInput 写入的备注可无损还原角度与标签', () => {
    const input = ideaToPlanInput(idea, { platform: 'xiaohongshu', publishDate: '2026-07-21' })
    expect(parsePlanNotes(input.notes || '')).toEqual({ angle: idea.angle, tags: idea.tags })
  })
})

describe('buildCreationTopicFromPlan 日历计划→创作主题文本', () => {
  it('标题 + 角度 + 标签拼成多行主题（与选题送创作格式一致）', () => {
    const topic = buildCreationTopicFromPlan(
      '新手减脂的 5 个常见误区',
      '切入角度：反常识盘点，击中新手焦虑\n建议标签：#减脂 #新手健身'
    )
    expect(topic).toBe(
      '新手减脂的 5 个常见误区\n切入角度：反常识盘点，击中新手焦虑\n建议标签：减脂 新手健身'
    )
  })

  it('备注无结构化信息时只保留标题', () => {
    expect(buildCreationTopicFromPlan('标题', '随手记的备注')).toBe('标题')
    expect(buildCreationTopicFromPlan('标题', '')).toBe('标题')
  })
})
