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
      <label class="filter-item">
        <span>清洗编号</span>
        <input v-model="keyword" placeholder="按清洗编号检索" />
      </label>
      <label class="filter-item">
        <span>清洗状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
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
            <template v-if="!isTerminal(row)">
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </template>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无组件清洗数据，可先登记清洗任务</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条组件清洗记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detailVisible" class="dialog-mask" @click.self="closeDetail">
      <div class="dialog-panel">
        <header class="dialog-head">
          <h3>{{ detailMode === 'create' ? '登记清洗任务' : `清洗任务详情 #${detailId}` }}</h3>
          <span v-if="detailMode === 'edit'" class="dialog-version">
            版本 {{ detailVersion }} · {{ detailStatus }}<template v-if="detailLocked">（已锁定）</template>
          </span>
        </header>
        <div class="dialog-body">
          <label v-for="field in editableFields" :key="field" class="dialog-field">
            <span>{{ field }}</span>
            <input v-model="detailForm[field]" :disabled="detailLocked" />
          </label>
          <label class="dialog-field">
            <span>清洗状态</span>
            <input :value="detailMode === 'create' ? '待清洗（登记后默认）' : detailStatus" disabled />
          </label>
        </div>
        <p v-if="detailMessage" class="error-text dialog-message">{{ detailMessage }}</p>
        <footer class="dialog-foot">
          <button v-if="detailMode === 'edit'" class="btn" type="button" @click="refreshDetail">载入最新数据</button>
          <button
            v-if="detailMode === 'edit' && !detailLocked"
            class="btn primary"
            type="button"
            @click="confirmDetail"
          >
            确认完成
          </button>
          <button v-if="!detailLocked" class="btn primary" type="button" @click="saveDetail">保存</button>
          <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/panel_clean'
const columns = ["清洗编号", "清洗区域", "组件数量", "清洗方式", "清洗日期", "清洗班组", "清洗效果", "清洗状态"]
const editableFields = columns.slice(0, 7)
const actions = ["安排清洗", "开始清洗", "确认完成"]
const statuses = ["待清洗", "清洗中", "已完成", "已取消"]
const terminalStatuses = ["已完成", "已取消"]
const stats = [{"label": "待清洗区域", "value": 0}, {"label": "清洗中区域", "value": 0}, {"label": "本月清洗量", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')

const detailVisible = ref(false)
const detailMode = ref<'create' | 'edit'>('edit')
const detailId = ref<number | null>(null)
const detailVersion = ref(1)
const detailStatus = ref('')
const detailLocked = ref(false)
const detailForm = ref<Record<string, string | number>>({})
const detailMessage = ref('')

function isTerminal(row: Row) {
  return terminalStatuses.includes(String(row['清洗状态'] ?? ''))
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function applyEntry(entry: Row) {
  detailId.value = Number(entry.id)
  detailVersion.value = Number(entry.version ?? 1)
  detailStatus.value = String(entry['清洗状态'] ?? '')
  detailLocked.value = terminalStatuses.includes(detailStatus.value)
  const form: Record<string, string | number> = {}
  for (const field of editableFields) {
    const value = entry[field]
    form[field] = value === null || value === undefined ? '' : value
  }
  detailForm.value = form
}

async function fetchDetail(id: number): Promise<Row | null> {
  const response = await request(`${ENDPOINT}/${id}`)
  if (!response.ok) {
    return null
  }
  return (await response.json()) as Row
}

async function openDetail(row: Row) {
  detailMessage.value = ''
  try {
    const entry = await fetchDetail(Number(row.id))
    if (!entry) {
      errorMessage.value = '清洗任务详情读取失败'
      return
    }
    detailMode.value = 'edit'
    applyEntry(entry)
    detailVisible.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '清洗任务详情读取失败'
  }
}

function openCreate() {
  detailMode.value = 'create'
  detailId.value = null
  detailVersion.value = 0
  detailStatus.value = statuses[0]
  detailLocked.value = false
  detailForm.value = {}
  detailMessage.value = ''
  detailVisible.value = true
}

function closeDetail() {
  detailVisible.value = false
}

async function refreshDetail() {
  if (detailId.value === null) {
    return
  }
  detailMessage.value = ''
  try {
    const entry = await fetchDetail(detailId.value)
    if (!entry) {
      detailMessage.value = '最新数据读取失败，请稍后重试'
      return
    }
    applyEntry(entry)
  } catch (error) {
    detailMessage.value = error instanceof Error ? error.message : '最新数据读取失败'
  }
}

async function saveDetail() {
  detailMessage.value = ''
  const isCreate = detailMode.value === 'create'
  const body: Record<string, unknown> = { values: detailForm.value }
  if (!isCreate) {
    body.version = detailVersion.value
  }
  try {
    const response = await request(isCreate ? ENDPOINT : `${ENDPOINT}/${detailId.value}`, {
      method: isCreate ? 'POST' : 'PUT',
      body: JSON.stringify(body),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      detailMessage.value = payload?.message ?? '清洗任务保存失败，请稍后重试'
      return
    }
    detailVisible.value = false
    await reload()
  } catch (error) {
    detailMessage.value = error instanceof Error ? error.message : '清洗任务保存失败'
  }
}

async function postAction(action: string, id: number): Promise<{ ok: boolean; message: string }> {
  const response = await request(`${ENDPOINT}/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ values: { action } }),
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok || !payload) {
    return { ok: false, message: '组件清洗动作未生效，请稍后重试' }
  }
  return { ok: Boolean(payload.ok), message: String(payload.message ?? '') }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const result = await postAction(action, Number(row.id))
    if (!result.ok) {
      errorMessage.value = result.message
      return
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '组件清洗操作失败'
  }
}

async function confirmDetail() {
  if (detailId.value === null) {
    return
  }
  detailMessage.value = ''
  try {
    const result = await postAction('确认完成', detailId.value)
    if (!result.ok) {
      detailMessage.value = result.message
      return
    }
    detailVisible.value = false
    await reload()
  } catch (error) {
    detailMessage.value = error instanceof Error ? error.message : '组件清洗操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) {
    query.set('keyword', keyword.value.trim())
  }
  if (statusFilter.value) {
    query.set('status', statusFilter.value)
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
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
.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.dialog-panel {
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  width: 560px;
  max-width: 92vw;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.18);
}
.dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.dialog-head h3 {
  margin: 0;
  font-size: 15px;
}
.dialog-version {
  color: var(--muted);
  font-size: 12px;
}
.dialog-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 14px;
}
.dialog-field span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 2px;
}
.dialog-field input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
}
.dialog-field input:disabled {
  background: #f1f5f9;
  color: var(--muted);
}
.dialog-message {
  margin: 10px 0 0;
  font-size: 13px;
}
.dialog-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
</style>
