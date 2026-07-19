import { getApiErrorPayload, http } from './client'
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
