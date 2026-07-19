import pluginVue from 'eslint-plugin-vue'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,mts,tsx,vue}']
  },
  {
    name: 'app/files-to-ignore',
    ignores: ['dist/**', 'node_modules/**', 'coverage/**']
  },
  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,
  skipFormatting,
  {
    name: 'app/rules-overrides',
    rules: {
      // 视图组件命名（HomeView 等）已是多词，个别单词组件放宽为警告
      'vue/multi-word-component-names': 'warn',
      // 存量代码逐步收敛 any，先警告不阻塞
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }
      ]
    }
  },
  {
    // 视图/组件（.vue）由独立维护，存量问题先降级为警告，避免阻塞 lint
    name: 'app/vue-legacy-relaxations',
    files: ['**/*.vue'],
    rules: {
      'prefer-const': 'warn',
      '@typescript-eslint/no-unused-vars': 'warn'
    }
  }
)
