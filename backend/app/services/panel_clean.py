"""组件清洗业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "panel_clean"
REQUIRED_FIELDS = ["清洗编号", "清洗区域", "组件数量"]
EDITABLE_FIELDS = ["清洗区域", "组件数量", "清洗方式", "清洗日期", "清洗班组", "清洗效果"]
STATUS_FIELD = "清洗状态"
STATUS_ORDER = ["待清洗", "清洗中", "已完成", "已取消"]
ACTION_RULES = {"安排清洗": "待清洗", "开始清洗": "清洗中", "确认完成": "已完成"}
DONE_STATUSES = {"已完成", "已取消"}
NEGATIVE_ACTIONS = []


class PanelCleanService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("清洗编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._identified(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._identified(entry)

    @staticmethod
    def _identified(entry: dict[str, Any]) -> dict[str, Any]:
        """保证每条记录都带稳定的版本号，列表、详情、保存都以 id + version 标识同一条记录。"""
        entry.setdefault("version", 1)
        return entry

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry[STATUS_FIELD] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["version"] = 1
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"清洗任务 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于组件清洗可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry[STATUS_FIELD] = target
        entry["pending"] = target not in DONE_STATUSES
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        entry["version"] = int(entry.get("version") or 1) + 1
        return entry, f"清洗任务已{action}"

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str, bool]:
        """按 id 原地保存详情；版本不符说明其他窗口已更新，拒绝覆盖并返回当前记录。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"清洗任务 {entry_id} 不存在或已归档", False
        current_version = int(entry.get("version") or 1)
        entry["version"] = current_version
        try:
            base_version = int(values.get("version"))
        except (TypeError, ValueError):
            base_version = current_version
        if base_version != current_version:
            return entry, (
                f"该清洗任务已在其他窗口更新（当前版本 v{current_version}），"
                "本次保存未生效，已保留最后一次有效确认，请刷新后重试"
            ), True
        for field in EDITABLE_FIELDS:
            if field in values:
                entry[field] = values[field]
        entry["version"] = current_version + 1
        return entry, "清洗任务已保存", False
