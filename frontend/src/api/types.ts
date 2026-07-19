import type { AppError } from '../utils/errors'

export interface Page {
  index: number
  type: 'cover' | 'content' | 'summary'
  content: string
}

export interface OutlineResponse {
  success: boolean
  outline?: string
  pages?: Page[]
  error?: AppError | string
  error_message?: string
}

export interface ProgressEvent {
  index: number
  status: 'generating' | 'done' | 'error'
  current?: number
  total?: number
  image_url?: string
  message?: string
  error?: AppError | string
  retryable?: boolean
}

export interface FinishEvent {
  success: boolean
  task_id: string
  images: string[]
  total?: number
  completed?: number
  failed?: number
  failed_indices?: number[]
  cached?: boolean
}

export interface HistoryRecord {
  id: string
  title: string
  created_at: string
  updated_at: string
  status: string
  thumbnail: string | null
  page_count: number
  task_id: string | null
}

export interface HistoryDetail {
  id: string
  title: string
  created_at: string
  updated_at: string
  outline: {
    raw: string
    pages: Page[]
  }
  images: {
    task_id: string | null
    generated: string[]
  }
  status: string
  thumbnail: string | null
}

export interface CreateHistoryParams {
  topic: string
  outline: { raw: string; pages: Page[] }
  task_id?: string
}

export interface UpdateHistoryParams {
  outline?: { raw: string; pages: Page[] }
  images?: { task_id: string | null; generated: string[] }
  status?: string
  thumbnail?: string
}

/**
 * 后端 /api/task/:taskId 返回的任务状态
 * generated/failed 的 key 是页面索引（JSON 序列化后为字符串）
 */
export interface TaskState {
  generated: Record<string, string>
  failed: Record<string, string>
  has_cover: boolean
}

/** 服务商配置项：字段因服务商类型而异，读取时再收敛具体类型 */
export type ProviderSettings = Record<string, unknown>

export interface Config {
  text_generation: {
    active_provider: string
    providers: Record<string, ProviderSettings>
  }
  image_generation: {
    active_provider: string
    providers: Record<string, ProviderSettings>
  }
}

export interface ContentResponse {
  success: boolean
  titles?: string[]
  copywriting?: string
  tags?: string[]
  error?: AppError | string
  error_message?: string
}
