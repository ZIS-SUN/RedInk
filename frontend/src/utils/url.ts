/**
 * URL 相关的纯函数工具
 */

/**
 * 向 URL 追加/覆盖一个查询参数，正确处理已带 query 的情况。
 * 支持相对路径（如 /api/images/xxx?thumbnail=true）和绝对 URL。
 *
 * @param rawUrl 原始 URL
 * @param key 参数名
 * @param value 参数值
 * @returns 追加参数后的 URL（相对路径保持相对形式）
 */
export function appendQueryParam(rawUrl: string, key: string, value: string): string {
  try {
    const isAbsolute = /^https?:\/\//i.test(rawUrl)
    const base = typeof window !== 'undefined' && window.location
      ? window.location.origin
      : 'http://localhost'
    const url = new URL(rawUrl, base)
    url.searchParams.set(key, value)
    return isAbsolute ? url.toString() : `${url.pathname}${url.search}${url.hash}`
  } catch {
    // 极端情况下退化为字符串拼接（仍然区分 ? 和 &）
    const sep = rawUrl.includes('?') ? '&' : '?'
    return `${rawUrl}${sep}${encodeURIComponent(key)}=${encodeURIComponent(value)}`
  }
}

/**
 * 给图片 URL 追加时间戳参数，避免浏览器缓存
 */
export function withCacheBuster(rawUrl: string): string {
  return appendQueryParam(rawUrl, 't', String(Date.now()))
}
