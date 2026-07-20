import { describe, expect, it } from 'vitest'
import {
  COMMENT_HANDOFF_KEY,
  setCommentHandoff,
  takeCommentHandoff,
  type SessionStorageLike,
} from '../commentHandoff'

/** 内存版 sessionStorage，用于测试注入 */
function memoryStorage(initial: Record<string, string> = {}): SessionStorageLike & { data: Record<string, string> } {
  const data = { ...initial }
  return {
    data,
    getItem: (key: string) => (key in data ? data[key]! : null),
    setItem: (key: string, value: string) => {
      data[key] = value
    },
    removeItem: (key: string) => {
      delete data[key]
    },
  }
}

describe('setCommentHandoff / takeCommentHandoff', () => {
  it('写入后取走，且读后即清', () => {
    const storage = memoryStorage()
    setCommentHandoff({ source: 'insight', comments: ['评论一', '评论二'] }, storage)

    const taken = takeCommentHandoff(storage)
    expect(taken).toEqual({ source: 'insight', comments: ['评论一', '评论二'] })
    // 读后即清：再取返回 null
    expect(takeCommentHandoff(storage)).toBeNull()
    expect(storage.data[COMMENT_HANDOFF_KEY]).toBeUndefined()
  })

  it('无数据 / 损坏数据 / 非法结构返回 null', () => {
    expect(takeCommentHandoff(memoryStorage())).toBeNull()
    expect(takeCommentHandoff(null)).toBeNull()
    expect(takeCommentHandoff(memoryStorage({ [COMMENT_HANDOFF_KEY]: '{{broken' }))).toBeNull()
    expect(
      takeCommentHandoff(memoryStorage({
        [COMMENT_HANDOFF_KEY]: JSON.stringify({ source: 'unknown', comments: ['x'] }),
      }))
    ).toBeNull()
    expect(
      takeCommentHandoff(memoryStorage({
        [COMMENT_HANDOFF_KEY]: JSON.stringify({ source: 'reply', comments: [] }),
      }))
    ).toBeNull()
  })
})
