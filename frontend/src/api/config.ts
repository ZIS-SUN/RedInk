import { LLM_TIMEOUT, http } from './client'
import type { Config } from './types'
import type { AppError } from '../utils/errors'

export async function getConfig(): Promise<{
  success: boolean
  config?: Config
  error?: AppError | string
  error_message?: string
}> {
  const response = await http.get('/config')
  return response.data
}

export async function updateConfig(config: Partial<Config>): Promise<{
  success: boolean
  message?: string
  error?: AppError | string
  error_message?: string
}> {
  const response = await http.post('/config', config)
  return response.data
}

export async function testConnection(config: {
  type: string
  provider_name?: string
  api_key?: string
  base_url?: string
  endpoint_type?: string
  model: string
}): Promise<{
  success: boolean
  message?: string
  error?: AppError | string
  error_message?: string
}> {
  // 连通性测试会真实请求上游 LLM，超时放宽
  const response = await http.post('/config/test', config, { timeout: LLM_TIMEOUT })
  return response.data
}
