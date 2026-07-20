/**
 * 目标搜索词（seo_keywords）请求参数测试：
 * - generateOutline：JSON 路径 / multipart 路径按约定携带 seo_keywords
 * - generateOutlineStream：请求体携带 seo_keywords
 * - generateContent / runChecklist：携带与省略逻辑
 * - 未填搜索词时请求体不携带该键（向后兼容）
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { generateOutline, generateOutlineStream, OutlineStreamFallbackError } from '../outline'
import { generateContent } from '../content'
import { runChecklist } from '../checklist'
import { http } from '../client'

// mock 掉网络层：只验证请求参数组装，不发真实请求
vi.mock('../client', () => ({
  API_BASE_URL: '/api',
  LLM_TIMEOUT: 1000,
  http: { post: vi.fn() },
  isAbortError: () => false,
  readSseResponse: vi.fn(),
  // 流式请求会合并部署级令牌头，测试环境无令牌返回空对象
  getAuthHeaders: () => ({})
}))

const mockPost = vi.mocked(http.post)

beforeEach(() => {
  mockPost.mockReset()
  mockPost.mockResolvedValue({ data: { success: true } })
})

describe('generateOutline（JSON 路径）', () => {
  it('填了搜索词时请求体携带 seo_keywords', async () => {
    await generateOutline('主题', undefined, 'brand-1', ['秋冬穿搭', '显瘦穿搭'])

    const [url, body] = mockPost.mock.calls[0]
    expect(url).toBe('/outline')
    expect(body).toEqual({
      topic: '主题',
      brand_id: 'brand-1',
      seo_keywords: ['秋冬穿搭', '显瘦穿搭']
    })
  })

  it('未填搜索词时请求体不携带 seo_keywords 键', async () => {
    await generateOutline('主题')

    const [, body] = mockPost.mock.calls[0]
    expect(body).toEqual({ topic: '主题' })
  })

  it('空数组等同未填，不携带该键', async () => {
    await generateOutline('主题', undefined, undefined, [])

    const [, body] = mockPost.mock.calls[0]
    expect(body).toEqual({ topic: '主题' })
  })
})

describe('generateOutline（multipart 路径）', () => {
  it('带图时搜索词以同名字段逐个追加到 FormData', async () => {
    const file = new File(['x'], 'ref.png', { type: 'image/png' })
    await generateOutline('主题', [file], undefined, ['秋冬穿搭', '显瘦穿搭'])

    const [url, body] = mockPost.mock.calls[0]
    expect(url).toBe('/outline')
    const formData = body as FormData
    expect(formData.getAll('seo_keywords')).toEqual(['秋冬穿搭', '显瘦穿搭'])
    expect(formData.get('topic')).toBe('主题')
  })

  it('带图但未填搜索词时 FormData 不含 seo_keywords 字段', async () => {
    const file = new File(['x'], 'ref.png', { type: 'image/png' })
    await generateOutline('主题', [file])

    const [, body] = mockPost.mock.calls[0]
    expect((body as FormData).getAll('seo_keywords')).toEqual([])
  })
})

describe('generateOutlineStream', () => {
  it('请求体携带 seo_keywords', async () => {
    // 返回非 2xx 让函数走回退信号路径：fetch 已发出，足以断言请求体
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 500 })
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      generateOutlineStream('主题', 'brand-1', {}, {}, ['秋冬穿搭'])
    ).rejects.toBeInstanceOf(OutlineStreamFallbackError)

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string)
    expect(body).toEqual({
      topic: '主题',
      brand_id: 'brand-1',
      seo_keywords: ['秋冬穿搭']
    })
  })

  it('未填搜索词时请求体不携带该键', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 500 })
    vi.stubGlobal('fetch', fetchMock)

    await expect(generateOutlineStream('主题')).rejects.toBeInstanceOf(
      OutlineStreamFallbackError
    )

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string)
    expect(body).toEqual({ topic: '主题' })
  })
})

describe('generateContent', () => {
  it('填了搜索词时请求体携带 seo_keywords', async () => {
    await generateContent('主题', '大纲', undefined, ['秋冬穿搭'])

    const [url, body] = mockPost.mock.calls[0]
    expect(url).toBe('/content')
    expect(body).toEqual({
      topic: '主题',
      outline: '大纲',
      seo_keywords: ['秋冬穿搭']
    })
  })

  it('未填搜索词时请求体与旧行为一致', async () => {
    await generateContent('主题', '大纲', 'brand-1')

    const [, body] = mockPost.mock.calls[0]
    expect(body).toEqual({ topic: '主题', outline: '大纲', brand_id: 'brand-1' })
  })
})

describe('runChecklist', () => {
  it('填了搜索词时请求体携带 seo_keywords', async () => {
    await runChecklist({
      platform: 'xiaohongshu',
      title: '标题',
      imageCount: 4,
      seoKeywords: ['秋冬穿搭']
    })

    const [url, body] = mockPost.mock.calls[0]
    expect(url).toBe('/checklist')
    expect(body).toEqual({
      platform: 'xiaohongshu',
      image_count: 4,
      title: '标题',
      seo_keywords: ['秋冬穿搭']
    })
  })

  it('未填搜索词时请求体不携带该键', async () => {
    await runChecklist({ platform: 'xiaohongshu', imageCount: 4 })

    const [, body] = mockPost.mock.calls[0]
    expect(body).toEqual({ platform: 'xiaohongshu', image_count: 4 })
  })
})
