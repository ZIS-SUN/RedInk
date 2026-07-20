import { describe, expect, it } from 'vitest'
import { DEFAULT_TIMEOUT, LLM_TIMEOUT, SSE_IDLE_TIMEOUT } from '../client'

/**
 * 超时对齐回归保护：
 * 后端上游单次请求预算 300 秒（backend/utils/text_client.py timeout=300、
 * backend/generators/* 统一 300_000ms），后端图片 SSE 心跳间隔 15 秒
 * （backend/services/image.py HEARTBEAT_INTERVAL_SECONDS）。
 * 前端超时被调小会导致「后端还在跑并扣费、前端已判失败」的假失败，
 * 用户重试等于重复扣费。
 */
const BACKEND_UPSTREAM_TIMEOUT_MS = 300_000
const BACKEND_HEARTBEAT_INTERVAL_MS = 15_000

describe('前后端超时对齐', () => {
  it('LLM 类接口超时覆盖后端单次上游最坏时长（300s）并留余量', () => {
    expect(LLM_TIMEOUT).toBeGreaterThan(BACKEND_UPSTREAM_TIMEOUT_MS)
  })

  it('SSE 空闲超时远大于后端心跳间隔（15s），心跳能可靠保活', () => {
    expect(SSE_IDLE_TIMEOUT).toBeGreaterThanOrEqual(BACKEND_HEARTBEAT_INTERVAL_MS * 4)
  })

  it('普通接口默认超时保持短超时（不受 LLM 超时放宽影响）', () => {
    expect(DEFAULT_TIMEOUT).toBeLessThanOrEqual(30_000)
  })
})
