import { getApiErrorPayload, http } from './client'
import type { AppError } from '../utils/errors'

/**
 * 发布助手 API
 * 约定：本模块的函数不抛异常，统一返回 { success: false, error, error_message }，
 * 错误归一化由统一 axios 实例的响应拦截器 + getApiErrorPayload 完成。
 *
 * 说明：发布助手是半自动工具——只管理账号标签、导出图片、备好文案，
 * 不保存密码、不自动登录、不自动发布。
 */

/** 平台账号（仅昵称/备注等标签信息，不含任何凭据） */
export interface PublishAccount {
  id: string
  /** 平台 key，如 "xiaohongshu" */
  platform: string
  nickname: string
  notes: string
  created_at: string
  updated_at: string
}

/** 支持的发布平台 */
export interface PublishPlatform {
  key: string
  label: string
  /** 创作者发布页地址，由用户手动打开 */
  creator_url: string
}

/** 备料返回的文案部分 */
export interface PublishPrepareText {
  titles: string[]
  copywriting: string
  tags: string[]
}

/** 备料结果：图片导出目录 + 文件名列表 + 文案 */
export interface PublishPrepareResult {
  /** 图片导出到的本地绝对路径 */
  folder: string
  files: string[]
  text: PublishPrepareText
}

export async function getPublishAccounts(): Promise<{
  success: boolean
  accounts: PublishAccount[]
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.get('/publish/accounts')
    return response.data
  } catch (error: unknown) {
    return { success: false, accounts: [], ...getApiErrorPayload(error, '获取账号列表失败') }
  }
}

export async function createPublishAccount(data: {
  platform: string
  nickname: string
  notes?: string
}): Promise<{
  success: boolean
  account?: PublishAccount
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.post('/publish/accounts', data)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '添加账号失败') }
  }
}

export async function updatePublishAccount(
  accountId: string,
  data: { platform?: string; nickname?: string; notes?: string }
): Promise<{
  success: boolean
  account?: PublishAccount
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.put(`/publish/accounts/${accountId}`, data)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '更新账号失败') }
  }
}

export async function deletePublishAccount(accountId: string): Promise<{
  success: boolean
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.delete(`/publish/accounts/${accountId}`)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '删除账号失败') }
  }
}

export async function getPublishPlatforms(): Promise<{
  success: boolean
  platforms: PublishPlatform[]
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.get('/publish/platforms')
    return response.data
  } catch (error: unknown) {
    return { success: false, platforms: [], ...getApiErrorPayload(error, '获取平台列表失败') }
  }
}

export async function preparePublishMaterial(recordId: string): Promise<{
  success: boolean
  folder?: string
  files?: string[]
  text?: PublishPrepareText
  error?: AppError | string
  error_message?: string
}> {
  try {
    // 导出图片可能较慢，放宽超时
    const response = await http.post('/publish/prepare', { record_id: recordId }, { timeout: 60_000 })
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '备料失败') }
  }
}

export async function openPublishFolder(path: string): Promise<{
  success: boolean
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.post('/publish/open-folder', { path })
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '打开文件夹失败') }
  }
}
