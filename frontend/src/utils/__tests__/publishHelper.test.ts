import { describe, expect, it } from 'vitest'
import {
  fileCountLabel,
  getPlatformMeta,
  hasPreparedFiles,
  isPrepareTextComplete,
  missingTextParts
} from '../publishHelper'

describe('getPlatformMeta', () => {
  it('已知平台 key 映射到中文 label 和色调', () => {
    expect(getPlatformMeta('xiaohongshu')).toEqual({ label: '小红书', tone: 'primary' })
    expect(getPlatformMeta('douyin')).toEqual({ label: '抖音', tone: 'neutral' })
    expect(getPlatformMeta('bilibili')).toEqual({ label: 'B站', tone: 'info' })
    expect(getPlatformMeta('kuaishou')).toEqual({ label: '快手', tone: 'warning' })
    expect(getPlatformMeta('weibo')).toEqual({ label: '微博', tone: 'danger' })
  })

  it('key 大小写与首尾空白不敏感', () => {
    expect(getPlatformMeta(' Douyin ')).toEqual({ label: '抖音', tone: 'neutral' })
    expect(getPlatformMeta('XIAOHONGSHU')).toEqual({ label: '小红书', tone: 'primary' })
  })

  it('后端 label 优先于内置映射', () => {
    expect(getPlatformMeta('xiaohongshu', '小红书（主号）').label).toBe('小红书（主号）')
  })

  it('未知 key 回退：label 用后端 label，其次 key 本身，色调 neutral', () => {
    expect(getPlatformMeta('toutiao', '头条号')).toEqual({ label: '头条号', tone: 'neutral' })
    expect(getPlatformMeta('toutiao')).toEqual({ label: 'toutiao', tone: 'neutral' })
  })

  it('key 为空 / null / undefined 时回退「未知平台」', () => {
    expect(getPlatformMeta('')).toEqual({ label: '未知平台', tone: 'neutral' })
    expect(getPlatformMeta(null)).toEqual({ label: '未知平台', tone: 'neutral' })
    expect(getPlatformMeta(undefined)).toEqual({ label: '未知平台', tone: 'neutral' })
    expect(getPlatformMeta('  ')).toEqual({ label: '未知平台', tone: 'neutral' })
  })
})

describe('hasPreparedFiles / fileCountLabel', () => {
  it('有文件时返回 true 和数量文案', () => {
    expect(hasPreparedFiles(['1.png', '2.png'])).toBe(true)
    expect(fileCountLabel(['1.png', '2.png', '3.png'])).toBe('共 3 张图片')
  })

  it('空数组 / null / undefined 时返回 false 与「暂无图片」', () => {
    expect(hasPreparedFiles([])).toBe(false)
    expect(hasPreparedFiles(null)).toBe(false)
    expect(hasPreparedFiles(undefined)).toBe(false)
    expect(fileCountLabel([])).toBe('暂无图片')
    expect(fileCountLabel(undefined)).toBe('暂无图片')
  })
})

describe('missingTextParts / isPrepareTextComplete', () => {
  const fullText = {
    titles: ['标题一', '标题二'],
    copywriting: '正文内容',
    tags: ['护肤', '干货']
  }

  it('文案齐备时无缺失', () => {
    expect(missingTextParts(fullText)).toEqual([])
    expect(isPrepareTextComplete(fullText)).toBe(true)
  })

  it('各块为空时逐一报缺失（顺序固定：标题/正文/标签）', () => {
    expect(missingTextParts({ ...fullText, titles: [] })).toEqual(['标题'])
    expect(missingTextParts({ ...fullText, copywriting: '' })).toEqual(['正文'])
    expect(missingTextParts({ ...fullText, tags: [] })).toEqual(['标签'])
    expect(missingTextParts({ titles: [], copywriting: '  ', tags: [] }))
      .toEqual(['标题', '正文', '标签'])
  })

  it('只含空白字符串视为空', () => {
    expect(isPrepareTextComplete({ titles: ['  '], copywriting: '正文', tags: ['a'] })).toBe(false)
    expect(isPrepareTextComplete({ titles: ['t'], copywriting: '\n\t', tags: ['a'] })).toBe(false)
    expect(isPrepareTextComplete({ titles: ['t'], copywriting: '正文', tags: [' '] })).toBe(false)
  })

  it('text 为 null / undefined 时全部缺失', () => {
    expect(missingTextParts(null)).toEqual(['标题', '正文', '标签'])
    expect(missingTextParts(undefined)).toEqual(['标题', '正文', '标签'])
    expect(isPrepareTextComplete(null)).toBe(false)
  })
})
