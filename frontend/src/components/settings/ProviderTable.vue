<template>
  <!-- 服务商列表表格 -->
  <div class="provider-table">
    <div class="table-header">
      <div class="col-status">状态</div>
      <div class="col-name">名称</div>
      <div class="col-model">模型</div>
      <div class="col-apikey">API Key</div>
      <div class="col-actions">操作</div>
    </div>
    <div
      v-for="(provider, name) in providers"
      :key="name"
      class="table-row"
      :class="{ active: activeProvider === name }"
    >
      <div class="col-status">
        <button
          class="btn-activate"
          :class="{ active: activeProvider === name }"
          @click="$emit('activate', name)"
          :disabled="activeProvider === name"
        >
          {{ activeProvider === name ? '已激活' : '激活' }}
        </button>
      </div>
      <div class="col-name">
        <span class="provider-name">{{ name }}</span>
      </div>
      <div class="col-model">
        <span class="model-name">{{ provider.model }}</span>
      </div>
      <div class="col-apikey">
        <span class="apikey-masked" :class="{ empty: !provider.api_key_masked }">
          {{ provider.api_key_masked || '未配置' }}
        </span>
      </div>
      <div class="col-actions">
        <button class="btn-icon" @click="$emit('test', name, provider)" title="测试连接">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
        </button>
        <button class="btn-icon" @click="$emit('edit', name, provider)" title="编辑">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
          </svg>
        </button>
        <button
          class="btn-icon danger"
          @click="$emit('delete', name)"
          v-if="canDelete"
          title="删除"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * 服务商列表表格组件
 *
 * 功能：
 * - 展示服务商列表
 * - 激活/编辑/删除/测试操作
 */

// 定义服务商类型
interface Provider {
  type: string
  model: string
  base_url?: string
  api_key?: string
  api_key_masked?: string
}

// 定义 Props
const props = defineProps<{
  providers: Record<string, Provider>
  activeProvider: string
}>()

// 定义 Emits
defineEmits<{
  (e: 'activate', name: string): void
  (e: 'edit', name: string, provider: Provider): void
  (e: 'delete', name: string): void
  (e: 'test', name: string, provider: Provider): void
}>()

// 是否可以删除（至少保留一个）
const canDelete = computed(() => Object.keys(props.providers).length > 1)
</script>

<style scoped>
/* 表格容器 */
.provider-table {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}

/* 表头 */
.table-header {
  display: grid;
  grid-template-columns: 80px 1fr 1fr 1.5fr 120px;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--gray-1);
  border-bottom: 1px solid var(--border-color);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

/* 表格行 */
.table-row {
  display: grid;
  grid-template-columns: 80px 1fr 1fr 1.5fr 120px;
  gap: var(--space-3);
  padding: 14px var(--space-4);
  border-bottom: 1px solid var(--border-color);
  align-items: center;
  transition: background var(--transition-fast), box-shadow var(--transition-fast);
}

.table-row:last-child {
  border-bottom: none;
}

.table-row:hover {
  background: var(--gray-0);
}

/* 当前激活行：主色微染 + 左侧细条强调，扫视时一眼可辨 */
.table-row.active {
  background: var(--primary-fade);
  box-shadow: inset 3px 0 0 var(--primary);
}

/* 激活按钮 */
.btn-activate {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  font-family: inherit;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-fast), box-shadow var(--transition-fast);
}

.btn-activate:hover:not(:disabled) {
  border-color: var(--border-hover);
  color: var(--primary);
  background: var(--primary-light);
  box-shadow: var(--shadow-xs);
}

/* 激活状态：语义 -soft 底 + 语义色文字 + 状态小圆点 */
.btn-activate.active {
  background: var(--color-success-soft);
  border-color: rgba(31, 169, 92, 0.3);
  color: var(--color-success);
  cursor: default;
}

.btn-activate.active::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: currentColor;
  flex-shrink: 0;
}

/* 服务商名称 */
.provider-name {
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

/* 模型名称 */
.model-name {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-sub);
  background: var(--gray-2);
  padding: 2px 6px;
  border-radius: var(--radius-xs);
}

/* API Key 显示 */
.apikey-masked {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  word-break: break-all;
}

.apikey-masked.empty {
  color: var(--color-warning);
}

/* 操作列 */
.col-actions {
  display: flex;
  gap: var(--space-2);
  justify-content: flex-end;
}

/* 图标按钮 */
.btn-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.btn-icon:hover {
  border-color: var(--border-hover);
  color: var(--primary);
  background: var(--primary-fade);
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

.btn-icon:active {
  transform: translateY(0);
  box-shadow: none;
}

.btn-icon.danger:hover {
  border-color: rgba(222, 59, 59, 0.35);
  color: var(--color-danger);
  background: var(--color-danger-soft);
}

/* 响应式：移动端改为横向滚动，保留全部列信息不丢失 */
@media (max-width: 768px) {
  .provider-table {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .table-header,
  .table-row {
    min-width: 620px;
  }
}
</style>
