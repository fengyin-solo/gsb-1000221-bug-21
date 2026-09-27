"""组件清洗业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "panel_clean"
REQUIRED_FIELDS = ["清洗编号", "清洗区域", "组件数量"]
EDITABLE_FIELDS = ["清洗编号", "清洗区域", "组件数量", "清洗方式", "清洗日期", "清洗班组", "清洗效果"]
STATUS_FIELD = "清洗状态"
STATUS_ORDER = ["待清洗", "清洗中", "已完成", "已取消"]
TERMINAL_STATUSES = {"已完成", "已取消"}
ACTION_RULES = {"安排清洗": "待清洗", "开始清洗": "清洗中", "确认完成": "已完成"}
NEGATIVE_ACTIONS: list[str] = []


class PanelCleanService:
    """清洗任务的记录标识约定：

    - `status` 是唯一的状态事实来源，`清洗状态` 只是它的展示副本，每次读写都保持同步；
    - `version` 随每次写入自增，保存时必须带上读取时的版本，旧会话整体回写会被拦下；
    - 终态（已完成/已取消）锁定，最后一次有效确认不会被后续保存或重复动作改回。
    """

    def _normalize(self, row: dict[str, Any]) -> dict[str, Any]:
        """让展示字段与规范状态对齐，并补齐版本号，保证列表与详情读到同一份事实。"""
        row.setdefault("version", 1)
        status = str(row.get("status") or STATUS_ORDER[0])
        row["status"] = status
        row[STATUS_FIELD] = status
        return row

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [self._normalize(row) for row in store.rows(MODULE)]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("清洗编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._normalize(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values[field] for field in EDITABLE_FIELDS if field in values})
        entry["status"] = STATUS_ORDER[0]
        entry[STATUS_FIELD] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["version"] = 1
        rows.append(entry)
        return entry, []

    def update_entry(
        self,
        entry_id: int,
        values: dict[str, Any],
        version: int | None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"清洗任务 {entry_id} 不存在或已归档"
        self._normalize(entry)
        current = int(entry["version"])
        if version is None or int(version) != current:
            return None, f"清洗任务已被其他窗口修改（当前版本 {current}），请刷新后再保存，本次修改未写入"
        if entry["status"] in TERMINAL_STATUSES:
            return None, f"清洗任务已{entry['status']}，最后一次确认结果已锁定，不能再回改"
        merged = dict(entry)
        merged.update({field: values[field] for field in EDITABLE_FIELDS if field in values})
        missing = [field for field in REQUIRED_FIELDS if not str(merged.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        entry.update({field: merged[field] for field in EDITABLE_FIELDS})
        entry["version"] = current + 1
        return entry, "清洗任务已保存"

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"清洗任务 {entry_id} 不存在或已归档"
        self._normalize(entry)
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于组件清洗可执行范围"
        if entry["status"] in TERMINAL_STATUSES:
            return None, f"清洗任务已{entry['status']}，最后一次确认结果已锁定，无需重复操作"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry[STATUS_FIELD] = target
        entry["pending"] = target not in TERMINAL_STATUSES
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        entry["version"] = int(entry["version"]) + 1
        return entry, f"清洗任务已{action}"
