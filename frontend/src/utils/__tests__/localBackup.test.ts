import { describe, expect, it } from 'vitest'
import {
  collectLocalBackup,
  LOCAL_BACKUP_KEYS,
  restoreLocalBackup,
  type BackupStorageLike
} from '../localBackup'

function makeStorage(initial: Record<string, string> = {}): {
  storage: BackupStorageLike
  data: Record<string, string>
} {
  const data = { ...initial }
  return {
    storage: {
      getItem: key => (key in data ? data[key] : null),
      setItem: (key, value) => {
        data[key] = value
      }
    },
    data
  }
}

describe('collectLocalBackup 收集', () => {
  it('只收集白名单内已有值的 key', () => {
    const { storage } = makeStorage({
      redink_custom_styles: '[{"id":"s1"}]',
      redink_export_watermark: '{"text":"@me"}',
      redink_unrelated_key: 'x'
    })

    const result = collectLocalBackup(storage)
    expect(result).toEqual({
      redink_custom_styles: '[{"id":"s1"}]',
      redink_export_watermark: '{"text":"@me"}'
    })
  })

  it('全部为空时返回空对象', () => {
    const { storage } = makeStorage()
    expect(collectLocalBackup(storage)).toEqual({})
  })

  it('storage 不可用时返回空对象', () => {
    expect(collectLocalBackup(null)).toEqual({})
  })

  it('单个 key 读取抛异常不影响其余收集', () => {
    const storage: BackupStorageLike = {
      getItem: key => {
        if (key === 'redink_active_style') throw new Error('blocked')
        return key === 'redink_custom_styles' ? '[]' : null
      },
      setItem: () => {}
    }
    expect(collectLocalBackup(storage)).toEqual({ redink_custom_styles: '[]' })
  })
})

describe('restoreLocalBackup 恢复', () => {
  it('恢复白名单键值并返回条数', () => {
    const { storage, data } = makeStorage()
    const restored = restoreLocalBackup(
      {
        redink_custom_styles: '[{"id":"s1"}]',
        redink_benchmark_history: '[]'
      },
      storage
    )
    expect(restored).toBe(2)
    expect(data.redink_custom_styles).toBe('[{"id":"s1"}]')
    expect(data.redink_benchmark_history).toBe('[]')
  })

  it('忽略白名单外的 key 与非字符串值', () => {
    const { storage, data } = makeStorage()
    const restored = restoreLocalBackup(
      {
        evil_key: 'x',
        redink_custom_styles: 123,
        redink_export_watermark: '{"text":"ok"}'
      },
      storage
    )
    expect(restored).toBe(1)
    expect(data).toEqual({ redink_export_watermark: '{"text":"ok"}' })
  })

  it('非对象输入返回 0 且不写入', () => {
    const { storage, data } = makeStorage()
    expect(restoreLocalBackup(null, storage)).toBe(0)
    expect(restoreLocalBackup('bad', storage)).toBe(0)
    expect(restoreLocalBackup(['a'], storage)).toBe(0)
    expect(data).toEqual({})
  })

  it('storage 不可用时返回 0', () => {
    expect(restoreLocalBackup({ redink_custom_styles: '[]' }, null)).toBe(0)
  })

  it('单条写入失败不中断其余恢复', () => {
    const written: Record<string, string> = {}
    const storage: BackupStorageLike = {
      getItem: () => null,
      setItem: (key, value) => {
        if (key === 'redink_active_style') throw new Error('quota')
        written[key] = value
      }
    }
    const restored = restoreLocalBackup(
      {
        redink_active_style: '{"id":"s0"}',
        redink_custom_styles: '[]'
      },
      storage
    )
    expect(restored).toBe(1)
    expect(written).toEqual({ redink_custom_styles: '[]' })
  })
})

describe('白名单与恢复往返', () => {
  it('collect 的结果 restore 后能完整写回', () => {
    const source = makeStorage(
      Object.fromEntries(LOCAL_BACKUP_KEYS.map((key, i) => [key, `value-${i}`]))
    )
    const backup = collectLocalBackup(source.storage)
    expect(Object.keys(backup)).toHaveLength(LOCAL_BACKUP_KEYS.length)

    const target = makeStorage()
    expect(restoreLocalBackup(backup, target.storage)).toBe(LOCAL_BACKUP_KEYS.length)
    expect(target.data).toEqual(source.data)
  })
})
