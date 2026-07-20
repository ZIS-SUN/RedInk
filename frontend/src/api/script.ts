import { LLM_TIMEOUT, http } from './client'
import type { AppError } from '../utils/errors'

/** 支持的时长档位代号 */
export type ScriptDuration = '30s' | '60s' | '3min'

/** 支持的场景类型代号 */
export type ScriptScene = 'talking_head' | 'voiceover' | 'drama'

/** 单段分镜 */
export interface ScriptSegment {
  /** 时间区间，如 "0-3s" */
  time_range: string
  /** 画面提示 */
  visual: string
  /** 口播台词 */
  voiceover: string
  /** 字幕断句建议 */
  subtitle_notes: string
}

/** 完整口播视频脚本 */
export interface VideoScript {
  /** 片名/选题建议 */
  title: string
  /** 前 3 秒钩子文案 */
  hook: string
  /** BGM 情绪建议 */
  bgm_mood: string
  /** 时长档位代号 */
  duration: ScriptDuration | string
  /** 场景类型代号 */
  scene: ScriptScene | string
  /** 时间轴分镜列表 */
  segments: ScriptSegment[]
  /** 结尾 CTA 话术 */
  cta: string
}

export interface ScriptResponse {
  success: boolean
  script?: VideoScript
  error?: AppError | string
  error_message?: string
}

/**
 * 口播视频脚本生成
 *
 * @param content 图文内容（正文/大纲）或主题
 * @param duration 时长档位代号（30s/60s/3min）
 * @param scene 场景类型代号（talking_head/voiceover/drama）
 * @param brandId 品牌档案 ID（可选），提供时后端按品牌人设约束生成
 */
export async function generateScript(
  content: string,
  duration: ScriptDuration,
  scene: ScriptScene,
  brandId?: string
): Promise<ScriptResponse> {
  const response = await http.post<ScriptResponse>(
    '/script',
    {
      content,
      duration,
      scene,
      ...(brandId ? { brand_id: brandId } : {})
    },
    // 脚本生成走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
