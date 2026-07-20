<template>
  <div class="dialog-mask" @click.self="handleClose">
    <div class="card calendar-dialog" role="dialog" aria-modal="true" aria-labelledby="add-calendar-title">
      <h3 id="add-calendar-title" class="dialog-title">加入内容日历</h3>
      <p class="dialog-idea-title">{{ idea.title }}</p>

      <div class="dialog-field">
        <label class="dialog-label" for="add-calendar-date">发布日期</label>
        <input
          id="add-calendar-date"
          v-model="publishDate"
          class="dialog-input"
          type="date"
          :disabled="saving"
        />
      </div>

      <div class="dialog-field">
        <label class="dialog-label" for="add-calendar-platform">发布平台</label>
        <select
          id="add-calendar-platform"
          v-model="platform"
          class="dialog-input"
          :disabled="saving"
        >
          <option v-for="p in PLATFORM_OPTIONS" :key="p.value" :value="p.value">
            {{ p.label }}
          </option>
        </select>
      </div>

      <div class="dialog-field">
        <label class="dialog-label" for="add-calendar-time">发布时间</label>
        <input
          id="add-calendar-time"
          v-model="publishTime"
          class="dialog-input"
          type="time"
          :disabled="saving"
        />
        <p v-if="suggestionApplied" class="dialog-hint">已按你的账号数据推荐最佳发布时段</p>
      </div>

      <p v-if="formError" class="dialog-error" role="alert">{{ formError }}</p>

      <div class="dialog-actions">
        <button type="button" class="btn btn-secondary" :disabled="saving" @click="handleClose">
          取消
        </button>
        <button
          type="button"
          class="btn btn-primary"
          :disabled="saving || !publishDate"
          @click="handleConfirm"
        >
          <span v-if="saving" class="spinner-sm" aria-hidden="true"></span>
          {{ saving ? '正在加入…' : '加入日历' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { createPlan, type PlanItem, type PlanPlatform } from '../../api/calendar'
import { getAnalyticsStats } from '../../api/analytics'
import { pickBestTimeSlot, slotToSuggestedTime } from '../../utils/calendarSuggest'
import {
  DEFAULT_PUBLISH_TIME,
  ideaToPlanInput,
  tomorrowDateStr,
  type CalendarIdeaLike,
} from '../../utils/ideaArchive'

const props = defineProps<{
  /** 要加入日历的选题（标题 / 切入角度 / 建议标签） */
  idea: CalendarIdeaLike
  /** 默认选中的平台（来自工具页的平台选择，未知平台时用小红书） */
  defaultPlatform?: PlanPlatform | null
}>()

const emit = defineEmits<{
  close: []
  added: [plan: PlanItem | undefined]
}>()

const PLATFORM_OPTIONS: Array<{ value: PlanPlatform; label: string }> = [
  { value: 'xiaohongshu', label: '小红书' },
  { value: 'douyin', label: '抖音' },
  { value: 'gongzhonghao', label: '公众号' },
  { value: 'bilibili', label: 'B站' },
  { value: 'shipinhao', label: '视频号' },
]

const publishDate = ref(tomorrowDateStr())
const platform = ref<PlanPlatform>(props.defaultPlatform || 'xiaohongshu')
const publishTime = ref(DEFAULT_PUBLISH_TIME)
const suggestionApplied = ref(false)
const saving = ref(false)
const formError = ref('')

/** 最佳时段建议的模块级缓存（undefined 表示尚未拉取；null 表示无可用建议） */
let cachedSuggestedTime: string | null | undefined

/**
 * 复用日历「最佳时段推荐」：拉取账号时段统计并取互动率最高时段的起始整点。
 * 拉取失败或无数据时静默回退默认 19:00。
 */
async function loadSuggestedTime(): Promise<string | null> {
  if (cachedSuggestedTime !== undefined) return cachedSuggestedTime
  const res = await getAnalyticsStats()
  const best = res.success && res.stats ? pickBestTimeSlot(res.stats.time_slots) : null
  cachedSuggestedTime = best ? slotToSuggestedTime(best.name) : null
  return cachedSuggestedTime
}

onMounted(async () => {
  const suggested = await loadSuggestedTime()
  // 用户已手动改过时间则不覆盖
  if (suggested && publishTime.value === DEFAULT_PUBLISH_TIME) {
    publishTime.value = suggested
    suggestionApplied.value = true
  }
})

function handleClose() {
  if (saving.value) return
  emit('close')
}

async function handleConfirm() {
  if (!publishDate.value || saving.value) return

  saving.value = true
  formError.value = ''

  const res = await createPlan(
    ideaToPlanInput(props.idea, {
      platform: platform.value,
      publishDate: publishDate.value,
      publishTime: publishTime.value,
    })
  )
  saving.value = false

  if (res.success) {
    emit('added', res.plan)
  } else {
    formError.value = res.error_message || '加入日历失败，请稍后重试'
  }
}
</script>

<style scoped>
.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
  padding: 16px;
  animation: fadeIn 0.2s var(--ease-out);
}

.calendar-dialog {
  width: min(440px, 100%);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.dialog-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-main);
  margin: 0;
}

.dialog-idea-title {
  font-size: 13.5px;
  color: var(--text-sub);
  line-height: 1.6;
  margin: 0;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--gray-1);
  word-break: break-word;
}

.dialog-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dialog-label {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-main);
}

.dialog-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: inherit;
  color: var(--text-main);
  background: var(--bg-card);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.dialog-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.dialog-hint {
  margin: 0;
  font-size: 12.5px;
  color: var(--primary);
}

.dialog-error {
  margin: 0;
  font-size: 13px;
  color: var(--color-danger);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .dialog-mask {
    animation: none;
  }
}
</style>
