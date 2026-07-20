import { describe, expect, it } from 'vitest'
import {
  collectLocalBackup,
  LOCAL_BACKUP_KEYS,
  restoreLocalBackup,
  type BackupStorageLike
} from '../localBackup'
import { ACCESS_TOKEN_STORAGE_KEY } from '../../api/client'
import {
  ACTIVE_STYLE_STORAGE_KEY,
  CUSTOM_STYLES_STORAGE_KEY
} from '../../composables/useStyleLibrary'
import { BENCHMARK_HISTORY_KEY } from '../benchmarkHistory'
import { COMMENT_HANDOFF_KEY } from '../commentHandoff'
import { HOTSPOT_LAYER_STORAGE_KEY } from '../hotspotLayer'
import { INSIGHT_ARCHIVE_KEY, TOPIC_ARCHIVE_KEY } from '../ideaArchive'
import { PATTERN_LIBRARY_KEY } from '../patternLibrary'
import { SAFE_ZONE_SETTINGS_KEY } from '../safeZone'
import {
  COVER_ARCHIVE_KEY,
  REPLY_ARCHIVE_KEY,
  REWRITE_ARCHIVE_KEY,
  SCRIPT_ARCHIVE_KEY,
  TITLE_ARCHIVE_KEY
} from '../toolArchive'
import { WATERMARK_SETTINGS_KEY } from '../watermarkSettings'

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
      },
      removeItem: key => {
        delete data[key]
      }
    },
    data
  }
}

describe('LOCAL_BACKUP_KEYS 白名单完整性', () => {
  /**
   * 各源模块导出的「用户资产」键全集。
   * generator-state 是 stores/generator.ts 的内部常量（未导出，
   * 该文件归其他任务所有，不为导出而改动），此处用字面量对齐。
   */
  const EXPECTED_ASSET_KEYS = [
    ACTIVE_STYLE_STORAGE_KEY,
    CUSTOM_STYLES_STORAGE_KEY,
    BENCHMARK_HISTORY_KEY,
    WATERMARK_SETTINGS_KEY,
    HOTSPOT_LAYER_STORAGE_KEY,
    'generator-state',
    PATTERN_LIBRARY_KEY,
    TITLE_ARCHIVE_KEY,
    REWRITE_ARCHIVE_KEY,
    SCRIPT_ARCHIVE_KEY,
    REPLY_ARCHIVE_KEY,
    COVER_ARCHIVE_KEY,
    TOPIC_ARCHIVE_KEY,
    INSIGHT_ARCHIVE_KEY,
    SAFE_ZONE_SETTINGS_KEY
  ]

  it('与各源模块导出的资产键集合一致', () => {
    expect([...LOCAL_BACKUP_KEYS].sort()).toEqual([...EXPECTED_ASSET_KEYS].sort())
  })

  it('无重复键', () => {
    expect(new Set(LOCAL_BACKUP_KEYS).size).toBe(LOCAL_BACKUP_KEYS.length)
  })

  it('不包含访问令牌 / 一次性 handoff / dismiss 类 UI 状态键', () => {
    const excludedKeys = [
      ACCESS_TOKEN_STORAGE_KEY,
      COMMENT_HANDOFF_KEY,
      // dismiss 类键是组件内部常量（未导出），用字面量核对
      'redink_setup_banner_dismissed',
      'resume-banner-dismissed'
    ]
    for (const key of excludedKeys) {
      expect(LOCAL_BACKUP_KEYS).not.toContain(key)
    }
  })
})

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
      setItem: () => {},
      removeItem: () => {}
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
      },
      removeItem: () => {}
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

describe('restoreLocalBackup 白名单全量替换（与后端 core_data 恢复语义对齐）', () => {
  it('备份中缺席的白名单键被删除，存在的键被写入', () => {
    const { storage, data } = makeStorage({
      [BENCHMARK_HISTORY_KEY]: '[{"id":"deleted-on-source"}]',
      [CUSTOM_STYLES_STORAGE_KEY]: '[{"id":"stale"}]'
    })
    restoreLocalBackup({ [CUSTOM_STYLES_STORAGE_KEY]: '[{"id":"s2"}]' }, storage)
    expect(data[CUSTOM_STYLES_STORAGE_KEY]).toBe('[{"id":"s2"}]')
    expect(BENCHMARK_HISTORY_KEY in data).toBe(false)
  })

  it('非白名单键（含访问令牌 / handoff / dismiss）恢复前后原样保留', () => {
    const { storage, data } = makeStorage({
      [ACCESS_TOKEN_STORAGE_KEY]: 'secret-token',
      [COMMENT_HANDOFF_KEY]: '{"pending":true}',
      'resume-banner-dismissed': '1'
    })
    restoreLocalBackup({ [CUSTOM_STYLES_STORAGE_KEY]: '[]' }, storage)
    expect(data[ACCESS_TOKEN_STORAGE_KEY]).toBe('secret-token')
    expect(data[COMMENT_HANDOFF_KEY]).toBe('{"pending":true}')
    expect(data['resume-banner-dismissed']).toBe('1')
  })

  it('空备份 payload 清空全部白名单键但不动其他键', () => {
    const { storage, data } = makeStorage({
      ...Object.fromEntries(LOCAL_BACKUP_KEYS.map((key, i) => [key, `value-${i}`])),
      [ACCESS_TOKEN_STORAGE_KEY]: 'secret-token'
    })
    const restored = restoreLocalBackup({}, storage)
    expect(restored).toBe(0)
    expect(data).toEqual({ [ACCESS_TOKEN_STORAGE_KEY]: 'secret-token' })
  })

  it('白名单键的非字符串值视为缺席，本地旧值被删除', () => {
    const { storage, data } = makeStorage({
      [CUSTOM_STYLES_STORAGE_KEY]: '[{"id":"s1"}]'
    })
    restoreLocalBackup({ [CUSTOM_STYLES_STORAGE_KEY]: 123 }, storage)
    expect(CUSTOM_STYLES_STORAGE_KEY in data).toBe(false)
  })

  it('单条删除失败不中断其余键的清除与写入', () => {
    const removed: string[] = []
    const written: Record<string, string> = {}
    const storage: BackupStorageLike = {
      getItem: () => null,
      setItem: (key, value) => {
        written[key] = value
      },
      removeItem: key => {
        if (key === BENCHMARK_HISTORY_KEY) throw new Error('blocked')
        removed.push(key)
      }
    }
    const restored = restoreLocalBackup(
      { [CUSTOM_STYLES_STORAGE_KEY]: '[]' },
      storage
    )
    expect(restored).toBe(1)
    expect(written).toEqual({ [CUSTOM_STYLES_STORAGE_KEY]: '[]' })
    expect(removed).toHaveLength(LOCAL_BACKUP_KEYS.length - 2)
    expect(removed).not.toContain(BENCHMARK_HISTORY_KEY)
  })

  it('非对象输入视为无效备份，白名单键不被清除', () => {
    const { storage, data } = makeStorage({
      [CUSTOM_STYLES_STORAGE_KEY]: '[{"id":"s1"}]'
    })
    expect(restoreLocalBackup(null, storage)).toBe(0)
    expect(restoreLocalBackup(undefined, storage)).toBe(0)
    expect(restoreLocalBackup('bad', storage)).toBe(0)
    expect(data[CUSTOM_STYLES_STORAGE_KEY]).toBe('[{"id":"s1"}]')
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
