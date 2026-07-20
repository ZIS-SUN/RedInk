import { describe, expect, it } from 'vitest'
import {
  charUnits,
  normalizeTags,
  parseHexColor,
  parseOutlinePageToCard,
  pickTextColor,
  wrapCanvasText
} from '../cardStudio'

describe('parseOutlinePageToCard', () => {
  it('首行作为标题，剩余行作为正文', () => {
    const parsed = parseOutlinePageToCard('封面标题\n第一点\n第二点')
    expect(parsed.title).toBe('封面标题')
    expect(parsed.body).toBe('第一点\n第二点')
  })

  it('剥离 markdown 标题符与列表符', () => {
    const parsed = parseOutlinePageToCard('## 三个习惯\n- 早睡早起\n* 坚持运动\n• 多喝水')
    expect(parsed.title).toBe('三个习惯')
    expect(parsed.body).toBe('早睡早起\n坚持运动\n多喝水')
  })

  it('跳过空行，取第一处非空行为标题', () => {
    const parsed = parseOutlinePageToCard('\n\n  标题在这里  \n\n正文一\n\n正文二\n')
    expect(parsed.title).toBe('标题在这里')
    expect(parsed.body).toBe('正文一\n正文二')
  })

  it('只有一行时正文为空', () => {
    expect(parseOutlinePageToCard('只有标题')).toEqual({ title: '只有标题', body: '' })
  })

  it('空内容返回空标题空正文', () => {
    expect(parseOutlinePageToCard('')).toEqual({ title: '', body: '' })
    expect(parseOutlinePageToCard('  \n \n')).toEqual({ title: '', body: '' })
  })
})

describe('parseHexColor', () => {
  it('解析 6 位十六进制', () => {
    expect(parseHexColor('#EF2A45')).toEqual({ r: 239, g: 42, b: 69 })
  })

  it('解析 3 位缩写并支持无 # 前缀', () => {
    expect(parseHexColor('#fff')).toEqual({ r: 255, g: 255, b: 255 })
    expect(parseHexColor('1a1a1a')).toEqual({ r: 26, g: 26, b: 26 })
  })

  it('非法输入返回 null', () => {
    expect(parseHexColor('')).toBeNull()
    expect(parseHexColor('#12345')).toBeNull()
    expect(parseHexColor('red')).toBeNull()
  })
})

describe('pickTextColor', () => {
  it('浅底返回深字', () => {
    expect(pickTextColor('#FFFFFF')).toBe('#1a1a1a')
    expect(pickTextColor('#F7F1E5')).toBe('#1a1a1a')
    expect(pickTextColor('#fff')).toBe('#1a1a1a')
  })

  it('深底返回白字', () => {
    expect(pickTextColor('#000000')).toBe('#fff')
    expect(pickTextColor('#1E3A2F')).toBe('#fff')
    expect(pickTextColor('#EF2A45')).toBe('#fff')
  })

  it('非法颜色按浅底处理返回深字', () => {
    expect(pickTextColor('not-a-color')).toBe('#1a1a1a')
  })
})

describe('normalizeTags', () => {
  it('按逗号 / 空格 / 顿号拆分', () => {
    expect(normalizeTags('美食, 探店 穿搭，日常、生活')).toEqual([
      '美食',
      '探店',
      '穿搭',
      '日常',
      '生活'
    ])
  })

  it('剥离前导 # 并去重（保持首次出现顺序）', () => {
    expect(normalizeTags('#美食 ##美食 探店 #探店')).toEqual(['美食', '探店'])
  })

  it('空输入与纯分隔符返回空数组', () => {
    expect(normalizeTags('')).toEqual([])
    expect(normalizeTags(' ,， 、 ')).toEqual([])
    expect(normalizeTags('#')).toEqual([])
  })
})

describe('charUnits', () => {
  it('中文与全角标点计 1，半角字符计 0.5', () => {
    expect(charUnits('字')).toBe(1)
    expect(charUnits('，')).toBe(1)
    expect(charUnits('？')).toBe(1)
    expect(charUnits('a')).toBe(0.5)
    expect(charUnits('1')).toBe(0.5)
    expect(charUnits(' ')).toBe(0.5)
  })
})

describe('wrapCanvasText', () => {
  it('中文按字宽贪心断行', () => {
    expect(wrapCanvasText('一二三四五六七八九十', 4)).toEqual(['一二三四', '五六七八', '九十'])
  })

  it('半角字符按 0.5 单位计宽', () => {
    // 8 个 ascii = 4 单位，恰好一行
    expect(wrapCanvasText('abcdefgh', 4)).toEqual(['abcdefgh'])
    expect(wrapCanvasText('abcdefghi', 4)).toEqual(['abcdefgh', 'i'])
  })

  it('中英混排宽度累加', () => {
    // 每行上限 3 单位：中(1)+a(0.5)+b(0.5)+文(1) = 3 → 「中ab文」为一行
    expect(wrapCanvasText('中ab文字cd', 3)).toEqual(['中ab文', '字cd'])
  })

  it('保留显式换行且空行原样保留', () => {
    expect(wrapCanvasText('第一行\n\n第二行', 10)).toEqual(['第一行', '', '第二行'])
  })

  it('折行后的新行忽略行首空格', () => {
    expect(wrapCanvasText('一二三四 五六', 4)).toEqual(['一二三四', '五六'])
  })

  it('单字符超宽时也至少一字符成行（不死循环）', () => {
    expect(wrapCanvasText('中文', 0.5)).toEqual(['中', '文'])
  })

  it('maxUnitsPerLine <= 0 时仅按显式换行拆分', () => {
    expect(wrapCanvasText('很长的一行文字\n第二行', 0)).toEqual(['很长的一行文字', '第二行'])
  })

  it('空字符串返回空数组', () => {
    expect(wrapCanvasText('', 10)).toEqual([])
  })
})
