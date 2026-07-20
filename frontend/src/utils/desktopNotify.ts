/**
 * 桌面原生通知桥接（pywebview js_api）。
 *
 * 桌面版由 desktop.py 注入 window.pywebview.api.notify（走 osascript 系统通知）；
 * 浏览器环境没有该对象，直接返回 false，调用方无需区分环境。
 * pywebview 注入 window.pywebview 是异步的，但生成流程耗时数分钟，
 * 通知触发时注入早已完成，直接特性检测即可。
 */
/** pywebview 注入的桌面 API 形状（仅声明本模块用到的部分） */
interface PywebviewWindow {
  pywebview?: {
    api?: {
      notify?: (title: string, message: string) => Promise<unknown>
    }
  }
}

export async function notifyDesktop(title: string, message: string): Promise<boolean> {
  try {
    const api = (window as unknown as PywebviewWindow).pywebview?.api
    if (typeof api?.notify !== 'function') return false
    const result = await api.notify(title, message)
    return result === true
  } catch {
    return false
  }
}
