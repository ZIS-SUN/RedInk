import { describe, expect, it } from 'vitest'
import {
  SHARE_CODE_PREFIX,
  SHARE_LIMITS,
  decodeStyleShareCode,
  encodeStyleShareCode,
  resolveDuplicateName,
  type SharedStylePayload
} from '../styleShareCode'

/** 构造一个合法的自定义风格载荷（可按需覆盖字段） */
function makeStyle(overrides: Partial<SharedStylePayload> = {}): SharedStylePayload {
  return {
    name: '奶油胶感',
    category: '柔和',
    description: '奶油质感的柔和风格，适合治愈系内容',
    coverGradient: 'linear-gradient(135deg, #FDFCFB 0%, #E2D1C3 40%, #B0A695 100%)',
    colors: ['#FDFCFB', '#E2D1C3', '#B0A695', '#4A4238'],
    scenes: ['好物种草', '日常记录'],
    stylePrompt: '奶油胶质感设计，低饱和暖色，柔和光影，soft cream texture',
    ...overrides
  }
}

/** 手工构造指定 JSON 内容的分享码（用于测试字段级校验） */
function makeCode(payload: unknown): string {
  const bytes = new TextEncoder().encode(JSON.stringify(payload))
  let binary = ''
  for (const byte of bytes) {
    binary += String.fromCharCode(byte)
  }
  const base64url = btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${SHARE_CODE_PREFIX}.${base64url}`
}

describe('encodeStyleShareCode（编码）', () => {
  it('输出 RINK1. 前缀 + base64url 字符集', () => {
    const code = encodeStyleShareCode(makeStyle())
    expect(code.startsWith('RINK1.')).toBe(true)
    expect(/^RINK1\.[A-Za-z0-9_-]+$/.test(code)).toBe(true)
  })

  it('不序列化 id / custom 等白名单外字段', () => {
    const style = { ...makeStyle(), id: 'custom-123', custom: true } as SharedStylePayload
    const code = encodeStyleShareCode(style)
    const decoded = decodeStyleShareCode(code)
    expect(decoded.ok).toBe(true)
    if (decoded.ok) {
      expect('id' in decoded.style).toBe(false)
      expect('custom' in decoded.style).toBe(false)
    }
  })
})

describe('编码 -> 解码 round-trip', () => {
  it('普通中文风格完整还原', () => {
    const style = makeStyle()
    const result = decodeStyleShareCode(encodeStyleShareCode(style))
    expect(result).toEqual({ ok: true, style })
  })

  it('含 emoji 与特殊字符的字段完整还原', () => {
    const style = makeStyle({
      name: '梦幻少女心🌸✨',
      description: '粉紫渐变💜 云朵与星星点缀，"引号"与 <标签> 也要原样保留',
      scenes: ['节日祝福🎉', '萌宠日常🐱'],
      stylePrompt: '梦幻粉紫渐变，云朵🌥️星星⭐装饰，dreamy pastel — 50% 透明度'
    })
    const result = decodeStyleShareCode(encodeStyleShareCode(style))
    expect(result).toEqual({ ok: true, style })
  })

  it('容忍首尾空白与粘贴折行', () => {
    const style = makeStyle()
    const code = encodeStyleShareCode(style)
    // 模拟聊天软件折行：中间插入换行、首尾加空白
    const middle = Math.floor(code.length / 2)
    const wrapped = `  \n${code.slice(0, middle)}\n${code.slice(middle)} \t\n`
    const result = decodeStyleShareCode(wrapped)
    expect(result).toEqual({ ok: true, style })
  })
})

describe('decodeStyleShareCode（非法输入）', () => {
  it('空字符串 / 纯空白 -> invalid-format', () => {
    expect(decodeStyleShareCode('')).toMatchObject({ ok: false, error: 'invalid-format' })
    expect(decodeStyleShareCode('  \n\t ')).toMatchObject({ ok: false, error: 'invalid-format' })
  })

  it('随意文本 / 缺少载荷 -> invalid-format', () => {
    expect(decodeStyleShareCode('随便一段话')).toMatchObject({ ok: false, error: 'invalid-format' })
    expect(decodeStyleShareCode('RINK1.')).toMatchObject({ ok: false, error: 'invalid-format' })
    expect(decodeStyleShareCode('RINK1.abc!!!')).toMatchObject({
      ok: false,
      error: 'invalid-format'
    })
  })

  it('版本过新 -> unsupported-version', () => {
    expect(decodeStyleShareCode('RINK2.abcd')).toMatchObject({
      ok: false,
      error: 'unsupported-version'
    })
    expect(decodeStyleShareCode('RINK99.abcd')).toMatchObject({
      ok: false,
      error: 'unsupported-version'
    })
  })

  it('base64 载荷不是合法 JSON -> corrupt-data', () => {
    // 'abcd' 可以 base64 解码，但内容不是 JSON
    expect(decodeStyleShareCode('RINK1.abcd')).toMatchObject({ ok: false, error: 'corrupt-data' })
    // 截断的分享码：JSON 被拦腰砍断
    const code = encodeStyleShareCode(makeStyle())
    expect(decodeStyleShareCode(code.slice(0, code.length - 8))).toMatchObject({
      ok: false,
      error: 'corrupt-data'
    })
  })

  it('JSON 不是对象 -> invalid-fields', () => {
    expect(decodeStyleShareCode(makeCode(123))).toMatchObject({
      ok: false,
      error: 'invalid-fields'
    })
    expect(decodeStyleShareCode(makeCode(['a', 'b']))).toMatchObject({
      ok: false,
      error: 'invalid-fields'
    })
  })

  it('所有失败结果都带用户可读 message', () => {
    const inputs = ['', 'RINK2.abcd', 'RINK1.abcd', makeCode({})]
    for (const input of inputs) {
      const result = decodeStyleShareCode(input)
      expect(result.ok).toBe(false)
      if (!result.ok) {
        expect(result.message.length).toBeGreaterThan(0)
      }
    }
  })
})

describe('decodeStyleShareCode（字段校验与钳制）', () => {
  it('名称缺失 / 空白 / 超长 -> invalid-fields', () => {
    expect(decodeStyleShareCode(makeCode(makeStyle({ name: undefined as never })))).toMatchObject({
      ok: false,
      error: 'invalid-fields'
    })
    expect(decodeStyleShareCode(makeCode(makeStyle({ name: '   ' })))).toMatchObject({
      ok: false,
      error: 'invalid-fields'
    })
    expect(
      decodeStyleShareCode(makeCode(makeStyle({ name: '超'.repeat(SHARE_LIMITS.name + 1) })))
    ).toMatchObject({ ok: false, error: 'invalid-fields' })
  })

  it('提示词缺失 / 超长 -> invalid-fields', () => {
    expect(
      decodeStyleShareCode(makeCode(makeStyle({ stylePrompt: undefined as never })))
    ).toMatchObject({ ok: false, error: 'invalid-fields' })
    expect(
      decodeStyleShareCode(
        makeCode(makeStyle({ stylePrompt: 'p'.repeat(SHARE_LIMITS.stylePrompt + 1) }))
      )
    ).toMatchObject({ ok: false, error: 'invalid-fields' })
  })

  it('名称与提示词恰好达到上限 -> 成功', () => {
    const style = makeStyle({
      name: '满'.repeat(SHARE_LIMITS.name),
      stylePrompt: 'p'.repeat(SHARE_LIMITS.stylePrompt)
    })
    expect(decodeStyleShareCode(makeCode(style))).toMatchObject({ ok: true })
  })

  it('描述超长 -> 截断而非失败', () => {
    const result = decodeStyleShareCode(
      makeCode(makeStyle({ description: '长'.repeat(SHARE_LIMITS.description + 50) }))
    )
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.style.description).toHaveLength(SHARE_LIMITS.description)
    }
  })

  it('未知分类 -> 兜底为首个预设分类', () => {
    const result = decodeStyleShareCode(makeCode(makeStyle({ category: '不存在的分类' as never })))
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.style.category).toBe('简约')
    }
  })

  it('非法配色被过滤，全部非法时用兜底配色', () => {
    const mixed = decodeStyleShareCode(
      makeCode(makeStyle({ colors: ['#FFAA00', 'javascript:alert(1)', 'red', '#12'] }))
    )
    expect(mixed.ok).toBe(true)
    if (mixed.ok) {
      expect(mixed.style.colors).toEqual(['#FFAA00'])
    }

    const allBad = decodeStyleShareCode(makeCode(makeStyle({ colors: ['red', 'url(x)'] })))
    expect(allBad.ok).toBe(true)
    if (allBad.ok) {
      expect(allBad.style.colors).toEqual(['#FDFCFB', '#E2D1C3', '#B0A695', '#4A4238'])
    }
  })

  it('场景数量与单项长度钳制', () => {
    const scenes = Array.from({ length: 20 }, (_, i) => `场景${i}`.repeat(10))
    const result = decodeStyleShareCode(makeCode(makeStyle({ scenes })))
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.style.scenes).toHaveLength(SHARE_LIMITS.sceneCount)
      for (const scene of result.style.scenes) {
        expect(scene.length).toBeLessThanOrEqual(SHARE_LIMITS.sceneLength)
      }
    }
  })

  it('封面渐变超长 -> 用配色重建', () => {
    const result = decodeStyleShareCode(
      makeCode(makeStyle({ coverGradient: 'x'.repeat(SHARE_LIMITS.coverGradient + 1) }))
    )
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.style.coverGradient).toBe(
        'linear-gradient(135deg, #FDFCFB 0%, #E2D1C3 40%, #B0A695 100%)'
      )
    }
  })

  it('封面渐变含 url() 或非渐变函数 -> 用配色重建（防外部请求注入）', () => {
    const rebuilt = 'linear-gradient(135deg, #FDFCFB 0%, #E2D1C3 40%, #B0A695 100%)'
    const cases = [
      'url(https://evil.example/pixel.png)',
      'linear-gradient(red, blue), url(https://evil.example/x)',
      'red',
      'image-set(url(x.png) 1x)'
    ]
    for (const coverGradient of cases) {
      const result = decodeStyleShareCode(makeCode(makeStyle({ coverGradient })))
      expect(result.ok).toBe(true)
      if (result.ok) {
        expect(result.style.coverGradient).toBe(rebuilt)
      }
    }
  })

  it('合法的 radial / repeating 渐变 -> 原样保留', () => {
    const gradients = [
      'radial-gradient(circle, #FFF 0%, #000 100%)',
      'repeating-linear-gradient(45deg, #FFAA00 0 10px, #000 10px 20px)'
    ]
    for (const coverGradient of gradients) {
      const result = decodeStyleShareCode(makeCode(makeStyle({ coverGradient })))
      expect(result.ok).toBe(true)
      if (result.ok) {
        expect(result.style.coverGradient).toBe(coverGradient)
      }
    }
  })
})

describe('resolveDuplicateName（重名后缀）', () => {
  it('无冲突时原样返回', () => {
    expect(resolveDuplicateName('奶油胶感', ['莫兰迪', '赛博朋克'])).toBe('奶油胶感')
    expect(resolveDuplicateName('奶油胶感', [])).toBe('奶油胶感')
  })

  it('已存在同名 -> 追加 (2)', () => {
    expect(resolveDuplicateName('奶油胶感', ['奶油胶感'])).toBe('奶油胶感(2)')
  })

  it('(2) 也被占用 -> 递增到 (3)、(4)...', () => {
    expect(resolveDuplicateName('奶油胶感', ['奶油胶感', '奶油胶感(2)'])).toBe('奶油胶感(3)')
    expect(
      resolveDuplicateName('奶油胶感', ['奶油胶感', '奶油胶感(2)', '奶油胶感(3)', '奶油胶感(4)'])
    ).toBe('奶油胶感(5)')
  })
})
