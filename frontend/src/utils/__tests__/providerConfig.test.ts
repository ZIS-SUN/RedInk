import { describe, it, expect } from 'vitest'
import {
  hasConfiguredProvider,
  getProviderConfigStatus,
  isConfigRelatedError
} from '../providerConfig'
import type { Config } from '../../api/types'
import type { AppError } from '../errors'

function makeConfig(overrides: {
  textProviders?: Record<string, unknown>
  imageProviders?: Record<string, unknown>
} = {}): Config {
  return {
    text_generation: {
      active_provider: 'text-a',
      providers: (overrides.textProviders ?? {}) as Config['text_generation']['providers']
    },
    image_generation: {
      active_provider: 'image-a',
      providers: (overrides.imageProviders ?? {}) as Config['image_generation']['providers']
    }
  }
}

function makeError(overrides: Partial<AppError> = {}): AppError {
  return {
    type: 'https://redink.app/errors/unknown-error',
    code: 'UNKNOWN_ERROR',
    title: '操作失败',
    detail: '发生未知错误',
    suggestion: '请稍后重试',
    status: 500,
    retryable: true,
    ...overrides
  }
}

describe('hasConfiguredProvider', () => {
  it('空/缺失 providers 视为未配置', () => {
    expect(hasConfiguredProvider(undefined)).toBe(false)
    expect(hasConfiguredProvider(null)).toBe(false)
    expect(hasConfiguredProvider({})).toBe(false)
  })

  it('脱敏响应：api_key_masked 非空即视为已配置', () => {
    expect(
      hasConfiguredProvider({
        a: { api_key: '', api_key_masked: 'sk-...cdef' }
      })
    ).toBe(true)
  })

  it('脱敏响应：api_key 与 api_key_masked 均为空串视为未配置', () => {
    expect(
      hasConfiguredProvider({
        a: { api_key: '', api_key_masked: '' },
        b: { api_key: '', api_key_masked: '   ' }
      })
    ).toBe(false)
  })

  it('本地状态：api_key 有真实值也视为已配置', () => {
    expect(hasConfiguredProvider({ a: { api_key: 'sk-live-123' } })).toBe(true)
  })

  it('多个服务商中只要有一个配了 Key 即已配置', () => {
    expect(
      hasConfiguredProvider({
        empty: { api_key: '', api_key_masked: '' },
        filled: { api_key: '', api_key_masked: 'AI...xyz' }
      })
    ).toBe(true)
  })

  it('非对象的 provider 条目安全跳过', () => {
    expect(hasConfiguredProvider({ weird: null, other: 'oops' })).toBe(false)
  })
})

describe('getProviderConfigStatus', () => {
  it('config 为空时视为完全未配置', () => {
    const status = getProviderConfigStatus(undefined)
    expect(status.textConfigured).toBe(false)
    expect(status.imageConfigured).toBe(false)
    expect(status.anyConfigured).toBe(false)
    expect(status.fullyConfigured).toBe(false)
  })

  it('全新用户：两个分区都没有已配置服务商', () => {
    const status = getProviderConfigStatus(makeConfig())
    expect(status.anyConfigured).toBe(false)
  })

  it('只配了文本分区', () => {
    const status = getProviderConfigStatus(
      makeConfig({ textProviders: { a: { api_key_masked: 'sk-...ab' } } })
    )
    expect(status.textConfigured).toBe(true)
    expect(status.imageConfigured).toBe(false)
    expect(status.anyConfigured).toBe(true)
    expect(status.fullyConfigured).toBe(false)
  })

  it('文本 + 图片都配置了', () => {
    const status = getProviderConfigStatus(
      makeConfig({
        textProviders: { a: { api_key_masked: 'sk-...ab' } },
        imageProviders: { b: { api_key_masked: 'AI...cd' } }
      })
    )
    expect(status.fullyConfigured).toBe(true)
  })
})

describe('isConfigRelatedError', () => {
  it('空错误返回 false', () => {
    expect(isConfigRelatedError(null)).toBe(false)
    expect(isConfigRelatedError(undefined)).toBe(false)
  })

  it('AUTH_OR_PERMISSION 错误码视为配置类', () => {
    expect(
      isConfigRelatedError(
        makeError({ code: 'AUTH_OR_PERMISSION', title: 'API Key 或权限不可用' })
      )
    ).toBe(true)
  })

  it('识别"文本服务商 xxx 未配置 API Key"文案', () => {
    expect(
      isConfigRelatedError(
        makeError({ detail: '文本服务商 my_provider 未配置 API Key' })
      )
    ).toBe(true)
  })

  it('识别"API Key 未配置"与"请先填写并保存该服务商的 API Key"', () => {
    expect(isConfigRelatedError(makeError({ detail: 'API Key 未配置' }))).toBe(true)
    expect(
      isConfigRelatedError(
        makeError({ suggestion: '请先填写并保存该服务商的 API Key。' })
      )
    ).toBe(true)
  })

  it('识别"无服务商配置"与"激活服务商不存在"', () => {
    expect(isConfigRelatedError(makeError({ detail: '无服务商配置' }))).toBe(true)
    expect(isConfigRelatedError(makeError({ detail: '激活服务商不存在' }))).toBe(true)
  })

  it('识别"服务商 xxx 未配置 Base URL"', () => {
    expect(
      isConfigRelatedError(makeError({ detail: '服务商 doubao 未配置 Base URL' }))
    ).toBe(true)
  })

  it('普通网络/限流错误不属于配置类', () => {
    expect(
      isConfigRelatedError(
        makeError({ code: 'NETWORK_TIMEOUT', title: '网络请求超时', detail: '请求超时' })
      )
    ).toBe(false)
    expect(
      isConfigRelatedError(
        makeError({ code: 'RATE_LIMITED', title: '上游限流', detail: '429 Too Many Requests' })
      )
    ).toBe(false)
  })

  it('文案里出现"配置"但与未配置无关时不误判', () => {
    expect(
      isConfigRelatedError(
        makeError({ detail: '生成失败', suggestion: '请检查网络配置后重试。' })
      )
    ).toBe(false)
  })
})
