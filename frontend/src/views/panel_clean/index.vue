<template>
  <section class="page" data-module="panel_clean">
    <header class="page-head">
      <div>
        <h2>组件清洗管理</h2>
        <p class="page-desc">维护清洗任务，围绕清洗编号、清洗区域、组件数量、清洗方式做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记清洗任务</button>
        <button class="btn" type="button" @click="exportRows">导出组件清洗清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无组件清洗数据，可先登记清洗任务</td>
        </tr>
      </tbody>
    </table>

    <div v-if="detail" class="drawer-mask" @click.self="closeDetail">
      <aside class="drawer">
        <header class="drawer-head">
          <h3>清洗任务详情 · {{ detail.清洗编号 ?? `#${detail.id}` }}</h3>
          <span class="drawer-version">状态：{{ detail.清洗状态 ?? '—' }} · 版本 v{{ detail.version ?? 1 }}</span>
        </header>
        <div class="drawer-body">
          <label v-for="field in editableFields" :key="field" class="drawer-item">
            <span>{{ field }}</span>
            <input v-model="detail[field]" :placeholder="`请输入${field}`" />
          </label>
        </div>
        <footer class="drawer-foot">
          <div class="drawer-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="btn ghost"
              type="button"
              @click="runAction(action, detail)"
            >
              {{ action }}
            </button>
          </div>
          <div class="drawer-actions">
            <button class="btn primary" type="button" @click="saveDetail">保存</button>
            <button class="btn" type="button" @click="closeDetail">关闭</button>
          </div>
        </footer>
      </aside>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条组件清洗记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/panel_clean'
const columns = ["清洗编号", "清洗区域", "组件数量", "清洗方式", "清洗日期", "清洗班组", "清洗效果", "清洗状态"]
const actions = ["安排清洗", "开始清洗", "确认完成"]
const editableFields = ["清洗区域", "组件数量", "清洗方式", "清洗日期", "清洗班组", "清洗效果"]
const statuses = ["待清洗", "清洗中", "已完成", "已取消"]
const stats = [{"label": "待清洗区域", "value": 0}, {"label": "清洗中区域", "value": 0}, {"label": "本月清洗量", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const detail = ref<Row | null>(null)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '清洗任务登记入口尚未接入审批流'
}

function applyEntry(entry: Row) {
  // 记录标识：按 id 替换列表与详情里的同一条记录，不新增副本
  const index = rows.value.findIndex((row) => String(row.id) === String(entry.id))
  if (index >= 0) {
    rows.value.splice(index, 1, entry)
  }
  if (detail.value && String(detail.value.id) === String(entry.id)) {
    detail.value = { ...entry }
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('清洗任务详情读取失败')
    }
    detail.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '清洗任务详情读取失败'
  }
}

function closeDetail() {
  detail.value = null
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message ?? result.detail ?? '组件清洗动作未生效，请稍后重试')
    }
    if (result.entry) {
      applyEntry(result.entry as Row)
    }
    noticeMessage.value = result.message ?? `清洗任务已${action}`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '组件清洗操作失败'
  }
}

async function saveDetail() {
  if (!detail.value) {
    return
  }
  errorMessage.value = ''
  noticeMessage.value = ''
  const current = detail.value
  const values: Row = { version: Number(current.version ?? 1) }
  for (const field of editableFields) {
    values[field] = current[field] ?? ''
  }
  try {
    const response = await request(`${ENDPOINT}/${current.id}`, {
      method: 'PUT',
      body: JSON.stringify({ values }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      // 会话时序冲突：服务端已保留最后一次有效确认，用最新记录同步列表与详情
      if (result.entry) {
        applyEntry(result.entry as Row)
      }
      throw new Error(result.message ?? result.detail ?? '清洗任务保存失败')
    }
    if (result.entry) {
      applyEntry(result.entry as Row)
    }
    noticeMessage.value = result.message ?? '清洗任务已保存'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '清洗任务保存失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('清洗任务列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '组件清洗列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  justify-content: flex-end;
  z-index: 10;
}
.drawer {
  width: 360px;
  max-width: 90vw;
  background: #fff;
  height: 100%;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.drawer-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.drawer-head h3 {
  margin: 0;
  font-size: 15px;
}
.drawer-version {
  color: var(--muted);
  font-size: 12px;
}
.drawer-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  overflow-y: auto;
}
.drawer-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 2px;
}
.drawer-item input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.drawer-foot {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.drawer-actions {
  display: flex;
  gap: 8px;
}
.notice-text {
  color: #027a48;
}
</style>
