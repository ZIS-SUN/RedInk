import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import {
  ACCESS_TOKEN_STORAGE_KEY,
  ACCESS_TOKEN_UNAUTHORIZED_MESSAGE,
  clearAccessToken,
  getAccessToken,
  getAuthHeaders,
  http,
  readErrorResponse,
  reshapeUnauthorizedPayload,
  setAccessToken,
  type TokenStorageLike
} from '../client'
import type { AppError } from '../../utils/errors'

/** 内存版 localStorage，用于纯函数注入与 vi.stubGlobal */
function makeFakeStorage(initial: Record<string, string> = {}): TokenStorageLike {
  const map = new Map(Object.entries(initial))
  return {
    getItem: key => (map.has(key) ? (map.get(key) as string) : null),
    setItem: (key, value) => {
      map.set(key, value)
    },
    removeItem: key => {
      map.delete(key)
    }
  }
}

/** 后端部署级令牌 401 的标准响应体（backend/app.py _register_access_token_auth） */
function unauthorizedPayload() {
  return {
    success: false,
    error: {
      type: 'https://redink.app/errors/unauthorized',
      code: 'UNAUTHORIZED',
      title: '访问未授权',
      detail: '缺少或无效的访问令牌',
      suggestion: '请在请求头携带 Authorization: Bearer <token> 或 X-Access-Token: <token>',
      status: 401,
      retryable: false,
      diagnostics: {}
    },
    error_message: '访问未授权：请在请求头携带 Authorization: Bearer <token> 或 X-Access-Token: <token>'
  }
}

// ==================== 令牌存取纯函数 ====================

describe('令牌存取（注入存储）', () => {
  it('set → get → clear 往返', () => {
    const storage = makeFakeStorage()
    expect(getAccessToken(storage)).toBe('')

    setAccessToken('my-secret-token', storage)
    expect(getAccessToken(storage)).toBe('my-secret-token')

    clearAccessToken(storage)
    expect(getAccessToken(storage)).toBe('')
  })

  it('保存时去除首尾空白', () => {
    const storage = makeFakeStorage()
    setAccessToken('  padded-token \n', storage)
    expect(getAccessToken(storage)).toBe('padded-token')
  })

  it('保存空白串等价于清除', () => {
    const storage = makeFakeStorage({ [ACCESS_TOKEN_STORAGE_KEY]: 'old' })
    setAccessToken('   ', storage)
    expect(getAccessToken(storage)).toBe('')
  })

  it('存储不可用（null）时静默降级不抛错', () => {
    expect(() => setAccessToken('x', null)).not.toThrow()
    expect(getAccessToken(null)).toBe('')
    expect(() => clearAccessToken(null)).not.toThrow()
    expect(getAuthHeaders(null)).toEqual({})
  })

  it('存储读写抛异常时静默降级（隐私模式）', () => {
    const broken: TokenStorageLike = {
      getItem: () => {
        throw new Error('SecurityError')
      },
      setItem: () => {
        throw new Error('QuotaExceededError')
      },
      removeItem: () => {
        throw new Error('SecurityError')
      }
    }
    expect(getAccessToken(broken)).toBe('')
    expect(() => setAccessToken('x', broken)).not.toThrow()
    expect(() => clearAccessToken(broken)).not.toThrow()
  })
})

describe('getAuthHeaders', () => {
  it('无令牌返回空对象（本地用户零行为变化）', () => {
    expect(getAuthHeaders(makeFakeStorage())).toEqual({})
  })

  it('有令牌返回 X-Access-Token 头', () => {
    const storage = makeFakeStorage({ [ACCESS_TOKEN_STORAGE_KEY]: 'test123' })
    expect(getAuthHeaders(storage)).toEqual({ 'X-Access-Token': 'test123' })
  })
})

// ==================== axios 拦截器 ====================

describe('axios 拦截器', () => {
  let originalAdapter: typeof http.defaults.adapter

  beforeEach(() => {
    originalAdapter = http.defaults.adapter
  })

  afterEach(() => {
    http.defaults.adapter = originalAdapter
    vi.unstubAllGlobals()
  })

  /** 用捕获请求配置的假 adapter 替换真实网络层 */
  function installCaptureAdapter(): InternalAxiosRequestConfig[] {
    const captured: InternalAxiosRequestConfig[] = []
    http.defaults.adapter = async config => {
      captured.push(config)
      return {
        data: { success: true },
        status: 200,
        statusText: 'OK',
        headers: {},
        config
      } as AxiosResponse
    }
    return captured
  }

  /** 让 adapter 以指定响应体抛出 401 AxiosError */
  function install401Adapter(payload: unknown) {
    http.defaults.adapter = async config => {
      const response = {
        data: payload,
        status: 401,
        statusText: 'UNAUTHORIZED',
        headers: {},
        config
      } as AxiosResponse
      throw new AxiosError(
        'Request failed with status code 401',
        AxiosError.ERR_BAD_REQUEST,
        config,
        null,
        response
      )
    }
  }

  it('已保存令牌时每次请求注入 X-Access-Token', async () => {
    vi.stubGlobal(
      'localStorage',
      makeFakeStorage({ [ACCESS_TOKEN_STORAGE_KEY]: 'test123' })
    )
    const captured = installCaptureAdapter()

    await http.get('/history')

    expect(captured).toHaveLength(1)
    expect(captured[0].headers.get('X-Access-Token')).toBe('test123')
  })

  it('保存后无需重建实例即生效（每次请求重新读取）', async () => {
    const storage = makeFakeStorage()
    vi.stubGlobal('localStorage', storage)
    const captured = installCaptureAdapter()

    await http.get('/history')
    expect(captured[0].headers.get('X-Access-Token')).toBeUndefined()

    setAccessToken('late-token')
    await http.get('/history')
    expect(captured[1].headers.get('X-Access-Token')).toBe('late-token')
  })

  it('未保存令牌时不添加任何鉴权头（零行为变化）', async () => {
    vi.stubGlobal('localStorage', makeFakeStorage())
    const captured = installCaptureAdapter()

    await http.get('/history')

    expect(captured[0].headers.get('X-Access-Token')).toBeUndefined()
    expect(captured[0].headers.get('Authorization')).toBeUndefined()
  })

  it('部署级令牌 401 → appError 塑形为「到设置页填写」提示', async () => {
    vi.stubGlobal('localStorage', makeFakeStorage())
    install401Adapter(unauthorizedPayload())

    const error = await http.get('/history').then(
      () => {
        throw new Error('应当抛错')
      },
      (e: unknown) => e
    )

    const appError = (error as { appError?: AppError }).appError
    expect(appError?.code).toBe('UNAUTHORIZED')
    expect(appError?.detail).toBe(ACCESS_TOKEN_UNAUTHORIZED_MESSAGE)
    expect(appError?.retryable).toBe(false)
    // 原始后端 detail 保留在诊断信息里
    expect(appError?.diagnostics?.raw).toBe('缺少或无效的访问令牌')
  })

  it('上游服务商 401（AUTH_OR_PERMISSION）不被塑形', async () => {
    vi.stubGlobal('localStorage', makeFakeStorage())
    const upstream = {
      success: false,
      error: {
        type: 'https://redink.app/errors/auth-or-permission',
        code: 'AUTH_OR_PERMISSION',
        title: 'API Key 或权限不可用',
        detail: '服务商拒绝了当前请求。',
        suggestion: '请检查 API Key、账户权限、模型访问权限和余额。',
        status: 401,
        retryable: false,
        diagnostics: {}
      },
      error_message: 'API Key 或权限不可用：请检查 API Key。'
    }
    install401Adapter(upstream)

    const error = await http.get('/outline').then(
      () => {
        throw new Error('应当抛错')
      },
      (e: unknown) => e
    )

    const appError = (error as { appError?: AppError }).appError
    expect(appError?.code).toBe('AUTH_OR_PERMISSION')
    expect(appError?.detail).toBe('服务商拒绝了当前请求。')
  })
})

// ==================== 401 塑形与 SSE 错误读取 ====================

describe('reshapeUnauthorizedPayload', () => {
  it('UNAUTHORIZED 响应体替换为用户可行动的提示', () => {
    const reshaped = reshapeUnauthorizedPayload(unauthorizedPayload()) as {
      success: boolean
      error: AppError
      error_message: string
    }
    expect(reshaped.success).toBe(false)
    expect(reshaped.error.code).toBe('UNAUTHORIZED')
    expect(reshaped.error.detail).toBe(ACCESS_TOKEN_UNAUTHORIZED_MESSAGE)
    expect(reshaped.error_message).toContain(ACCESS_TOKEN_UNAUTHORIZED_MESSAGE)
  })

  it('非 UNAUTHORIZED / 非结构化数据原样返回', () => {
    const upstream = { error: { code: 'AUTH_OR_PERMISSION' } }
    expect(reshapeUnauthorizedPayload(upstream)).toBe(upstream)
    expect(reshapeUnauthorizedPayload(null)).toBe(null)
    expect(reshapeUnauthorizedPayload('oops')).toBe('oops')
  })
})

describe('readErrorResponse（SSE fetch 错误路径）', () => {
  it('部署级令牌 401 响应体同样被塑形', async () => {
    const response = new Response(JSON.stringify(unauthorizedPayload()), { status: 401 })
    const result = (await readErrorResponse(response, '请求失败')) as {
      error: AppError
    }
    expect(result.error.code).toBe('UNAUTHORIZED')
    expect(result.error.detail).toBe(ACCESS_TOKEN_UNAUTHORIZED_MESSAGE)
  })

  it('非 JSON 响应体回退为 fallback Error', async () => {
    const response = new Response('<html>bad gateway</html>', { status: 502 })
    const result = await readErrorResponse(response, '请求失败：HTTP 502')
    expect(result).toBeInstanceOf(Error)
    expect((result as Error).message).toBe('请求失败：HTTP 502')
  })
})
