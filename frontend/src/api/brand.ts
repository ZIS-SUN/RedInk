import { getApiErrorPayload, http, LLM_TIMEOUT } from './client'
import type { AppError } from '../utils/errors'

/**
 * 品牌风格记忆（品牌资料库）API
 * 约定：本模块的函数不抛异常，统一返回 { success: false, error, error_message }，
 * 错误归一化由统一 axios 实例的响应拦截器 + getApiErrorPayload 完成。
 */

/** 品牌档案 */
export interface BrandKit {
  id: string
  /** 品牌/IP 名称 */
  name: string
  /** 一句话定位 */
  tagline: string
  /** 目标人群 */
  audience: string
  /** 语气风格（如"专业克制"/"活泼种草"） */
  tone: string
  /** 常用口头禅/开场白 */
  catchphrases: string[]
  /** 签名/结尾话术 */
  signature: string
  /** 主色调（如 #FF2442） */
  primary_color: string
  /** 禁用词 */
  banned_words: string[]
  /** 备注 */
  notes: string
  created_at: string
  updated_at: string
}

/** 新建/更新档案时的入参（id 与时间戳由后端管理） */
export type BrandKitInput = Partial<Omit<BrandKit, 'id' | 'created_at' | 'updated_at'>> & {
  name: string
}

export async function getBrandList(): Promise<{
  success: boolean
  brands: BrandKit[]
  active_id: string | null
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.get('/brands')
    return response.data
  } catch (error: unknown) {
    return {
      success: false,
      brands: [],
      active_id: null,
      ...getApiErrorPayload(error, '获取品牌档案列表失败')
    }
  }
}

export async function createBrand(data: BrandKitInput): Promise<{
  success: boolean
  brand?: BrandKit
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.post('/brands', data)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '创建品牌档案失败') }
  }
}

export async function updateBrand(
  brandId: string,
  data: Partial<BrandKitInput>
): Promise<{
  success: boolean
  brand?: BrandKit
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.put(`/brands/${brandId}`, data)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '更新品牌档案失败') }
  }
}

export async function deleteBrand(brandId: string): Promise<{
  success: boolean
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.delete(`/brands/${brandId}`)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '删除品牌档案失败') }
  }
}

export async function activateBrand(brandId: string): Promise<{
  success: boolean
  active_id?: string
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.post(`/brands/${brandId}/activate`)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '启用品牌档案失败') }
  }
}

/** 起号选题（新手定位向导生成的前 10 篇发布清单条目） */
export interface BrandStarterTopic {
  /** 选题标题，可直接拿去创作 */
  title: string
  /** 切入角度：这条为什么适合起号期发 */
  angle: string
}

/** AI 生成的品牌档案草稿（新手账号定位向导） */
export interface BrandDraft {
  /** 账号名建议（2-3 个候选） */
  name: string[]
  /** 一句话定位 */
  positioning: string
  /** 语气风格描述 */
  tone: string
  /** 口头禅/开场白 */
  catchphrases: string[]
  /** 签名档/结尾话术 */
  signature: string
  /** 建议避免的词 */
  banned_words: string[]
  /** 赛道标签（3-5 个） */
  niche_tags: string[]
  /** 前 10 篇起号选题 */
  starter_topics: BrandStarterTopic[]
}

/** 新手定位向导的三个回答 */
export interface BrandDraftInput {
  /** 你是谁（身份/经历） */
  who: string
  /** 做给谁看（目标人群） */
  audience: string
  /** 凭什么是你（独特优势） */
  advantage: string
}

export async function generateBrandDraft(input: BrandDraftInput): Promise<{
  success: boolean
  draft?: BrandDraft
  error?: AppError | string
  error_message?: string
}> {
  try {
    // 定位草稿生成走 LLM，耗时较长
    const response = await http.post('/brand/draft', input, { timeout: LLM_TIMEOUT })
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '生成账号定位失败') }
  }
}

export async function getActiveBrand(): Promise<{
  success: boolean
  brand?: BrandKit | null
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.get('/brands/active')
    return response.data
  } catch (error: unknown) {
    return { success: false, brand: null, ...getApiErrorPayload(error, '获取当前启用档案失败') }
  }
}
