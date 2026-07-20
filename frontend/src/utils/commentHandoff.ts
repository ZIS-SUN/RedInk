/**
 * 评论洞察 ↔ 评论助手的评论互通（sessionStorage 传递）
 *
 * 两个工具的输入同构（粉丝评论每行一条）：
 * - 洞察页「用这批评论生成回复」→ 写入后跳 /tools/reply
 * - 回复页「用这批评论挖选题痛点」→ 写入后跳 /tools/insight
 * 目标页挂载时取走（读后即清，避免残留数据反复预填）。
 */

/** sessionStorage 键：目标页取评论用（两个方向共用一个键） */
export const COMMENT_HANDOFF_KEY = 'redink_comment_handoff'

/** 评论来源工具，用于目标页展示「来自 xx」提示 */
export type CommentHandoffSource = 'insight' | 'reply'

/** 一次评论互通传递的数据 */
export interface CommentHandoff {
  /** 评论来源工具 */
  source: CommentHandoffSource
  /** 评论列表（每项一条） */
  comments: string[]
}

/** sessionStorage 的最小接口，便于测试注入 */
export interface SessionStorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

function defaultStorage(): SessionStorageLike | null {
  return typeof sessionStorage === 'undefined' ? null : sessionStorage
}

/** 校验取出的数据结构（损坏数据整体丢弃） */
function isValidHandoff(value: unknown): value is CommentHandoff {
  if (typeof value !== 'object' || value === null) return false
  const h = value as Record<string, unknown>
  if (h.source !== 'insight' && h.source !== 'reply') return false
  if (!Array.isArray(h.comments) || h.comments.length === 0) return false
  return h.comments.every(c => typeof c === 'string')
}

/**
 * 写入一批评论供目标工具页预填（存储不可写时静默忽略，跳转仍继续）
 */
export function setCommentHandoff(
  handoff: CommentHandoff,
  storage: SessionStorageLike | null = defaultStorage()
): void {
  if (!storage) return
  try {
    storage.setItem(COMMENT_HANDOFF_KEY, JSON.stringify(handoff))
  } catch {
    // sessionStorage 不可写（隐私模式/配额满）时放弃传递，不阻塞跳转
  }
}

/**
 * 取走待预填的评论（读后即清）；无数据/损坏时返回 null
 */
export function takeCommentHandoff(
  storage: SessionStorageLike | null = defaultStorage()
): CommentHandoff | null {
  if (!storage) return null
  try {
    const raw = storage.getItem(COMMENT_HANDOFF_KEY)
    if (!raw) return null
    storage.removeItem(COMMENT_HANDOFF_KEY)

    const parsed: unknown = JSON.parse(raw)
    return isValidHandoff(parsed) ? parsed : null
  } catch {
    return null
  }
}
