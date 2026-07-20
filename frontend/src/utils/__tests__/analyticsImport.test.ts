import { describe, expect, it } from 'vitest'
import {
  cleanNumber,
  matchHeaderField,
  normalizeDate,
  normalizeTime,
  parseAnalyticsImport
} from '../analyticsImport'

describe('matchHeaderField（表头别名宽松匹配）', () => {
  it('精确别名', () => {
    expect(matchHeaderField('标题')).toBe('title')
    expect(matchHeaderField('平台')).toBe('platform')
    expect(matchHeaderField('日期')).toBe('publish_date')
    expect(matchHeaderField('发布时间')).toBe('publish_time')
    expect(matchHeaderField('类型')).toBe('content_type')
    expect(matchHeaderField('标签')).toBe('content_type')
    expect(matchHeaderField('曝光')).toBe('views')
    expect(matchHeaderField('播放')).toBe('views')
    expect(matchHeaderField('点赞')).toBe('likes')
    expect(matchHeaderField('收藏')).toBe('collects')
    expect(matchHeaderField('评论')).toBe('comments')
    expect(matchHeaderField('转发')).toBe('shares')
    expect(matchHeaderField('涨粉')).toBe('followers_gained')
  })

  it('模糊匹配：含空格、括号、量词后缀', () => {
    expect(matchHeaderField('曝光量(次)')).toBe('views')
    expect(matchHeaderField('播放量')).toBe('views')
    expect(matchHeaderField(' 点赞数 ')).toBe('likes')
    expect(matchHeaderField('发布日期')).toBe('publish_date')
    expect(matchHeaderField('内容类型')).toBe('content_type')
    expect(matchHeaderField('涨粉数')).toBe('followers_gained')
  })

  it('「发布时间」优先于「日期」不被误判', () => {
    expect(matchHeaderField('发布时间')).toBe('publish_time')
    expect(matchHeaderField('发布日期')).toBe('publish_date')
  })

  it('无法识别的表头返回 null', () => {
    expect(matchHeaderField('随便什么')).toBeNull()
    expect(matchHeaderField('')).toBeNull()
  })
})

describe('cleanNumber（数字清洗）', () => {
  it('去千分位逗号', () => {
    expect(cleanNumber('1,234')).toBe(1234)
    expect(cleanNumber('12，345')).toBe(12345)
  })

  it('万 -> *10000', () => {
    expect(cleanNumber('1.2万')).toBe(12000)
    expect(cleanNumber('3万')).toBe(30000)
    expect(cleanNumber('2.5w')).toBe(25000)
  })

  it('空值 / 无法解析 / 负数 -> 0', () => {
    expect(cleanNumber('')).toBe(0)
    expect(cleanNumber('abc')).toBe(0)
    expect(cleanNumber('-5')).toBe(0)
  })

  it('普通数字原样解析', () => {
    expect(cleanNumber('520')).toBe(520)
    expect(cleanNumber(' 88 ')).toBe(88)
  })
})

describe('normalizeDate / normalizeTime', () => {
  it('日期分隔符归一化并补零', () => {
    expect(normalizeDate('2026/7/1')).toBe('2026-07-01')
    expect(normalizeDate('2026.07.01')).toBe('2026-07-01')
    expect(normalizeDate('2026-07-01')).toBe('2026-07-01')
  })

  it('无法识别的日期原样返回', () => {
    expect(normalizeDate('7月1日')).toBe('7月1日')
  })

  it('时间归一化为 HH:MM', () => {
    expect(normalizeTime('21：30')).toBe('21:30')
    expect(normalizeTime('8:5')).toBe('08:05')
    expect(normalizeTime('20点15')).toBe('20:15')
  })

  it('无法识别 / 越界的时间返回空串', () => {
    expect(normalizeTime('')).toBe('')
    expect(normalizeTime('晚上')).toBe('')
    expect(normalizeTime('25:00')).toBe('')
  })
})

describe('parseAnalyticsImport（制表符分隔）', () => {
  const tsv = [
    '标题\t平台\t发布日期\t发布时间\t类型\t曝光\t点赞\t收藏\t评论\t转发\t涨粉',
    '敏感肌自救指南\t小红书\t2026/7/1\t20:30\t干货教程\t1.2万\t1,024\t300\t56\t18\t120',
    '',
    '夏日穿搭\t抖音\t2026-07-02\t\t日常vlog\t8000\t500\t100\t20\t10\t30'
  ].join('\n')

  it('识别 tab 分隔并解析全部字段', () => {
    const result = parseAnalyticsImport(tsv)
    expect(result.delimiter).toBe('tab')
    expect(result.errors).toEqual([])
    expect(result.records).toHaveLength(2)

    expect(result.records[0]).toEqual({
      title: '敏感肌自救指南',
      platform: '小红书',
      publish_date: '2026-07-01',
      publish_time: '20:30',
      content_type: '干货教程',
      views: 12000,
      likes: 1024,
      collects: 300,
      comments: 56,
      shares: 18,
      followers_gained: 120
    })
    expect(result.records[1].publish_time).toBe('')
  })

  it('空行被跳过', () => {
    const result = parseAnalyticsImport(tsv)
    expect(result.records).toHaveLength(2)
  })
})

describe('parseAnalyticsImport（CSV 逗号分隔）', () => {
  it('解析 CSV 并支持带引号的单元格', () => {
    const csv = [
      '标题,平台,曝光,点赞',
      '"你好，世界",小红书,"1,500",66'
    ].join('\n')

    const result = parseAnalyticsImport(csv)
    expect(result.delimiter).toBe('comma')
    expect(result.errors).toEqual([])
    expect(result.records).toEqual([
      { title: '你好，世界', platform: '小红书', views: 1500, likes: 66 }
    ])
  })
})

describe('parseAnalyticsImport（错误收集）', () => {
  it('缺标题 / 缺平台的行收集为错误且不中断其他行', () => {
    const text = [
      '标题\t平台\t曝光',
      '\t小红书\t100',
      '正常行\t抖音\t200',
      '没有平台\t\t300'
    ].join('\n')

    const result = parseAnalyticsImport(text)
    expect(result.records).toHaveLength(1)
    expect(result.records[0].title).toBe('正常行')
    expect(result.errors).toHaveLength(2)
    expect(result.errors[0]).toEqual({ line: 2, reason: '缺少标题' })
    expect(result.errors[1]).toEqual({ line: 4, reason: '缺少平台' })
  })

  it('表头缺少必需列时返回表头错误', () => {
    const result = parseAnalyticsImport('日期\t曝光\n2026-07-01\t100')
    expect(result.records).toEqual([])
    expect(result.errors).toHaveLength(1)
    expect(result.errors[0].line).toBe(1)
    expect(result.errors[0].reason).toContain('标题')
    expect(result.errors[0].reason).toContain('平台')
  })

  it('无法识别的列被忽略，不影响其他列', () => {
    const result = parseAnalyticsImport('标题\t平台\t神秘列\t点赞\nA\t小红书\txxx\t10')
    expect(result.records).toEqual([{ title: 'A', platform: '小红书', likes: 10 }])
    expect(result.headerFields).toEqual(['title', 'platform', null, 'likes'])
  })

  it('纯空文本返回空结果', () => {
    const result = parseAnalyticsImport('  \n \n')
    expect(result.records).toEqual([])
    expect(result.errors).toEqual([])
  })
})
