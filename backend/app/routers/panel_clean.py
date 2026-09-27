"""组件清洗接口：维护清洗任务，覆盖安排清洗、开始清洗、确认完成等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.panel_clean import PanelCleanService

router = APIRouter(prefix="/api/panel_clean", tags=["组件清洗"])

service = PanelCleanService()

LIST_FIELDS = ["清洗编号", "清洗区域", "组件数量", "清洗方式", "清洗日期", "清洗班组", "清洗效果", "清洗状态"]
STATUSES = ["待清洗", "清洗中", "已完成", "已取消"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按清洗编号检索"),
    status: str | None = Query(default=None, description="待清洗、清洗中、已完成、已取消"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按清洗编号与状态过滤组件清洗列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出组件清洗清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "panel_clean", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条清洗任务明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"清洗任务 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条清洗任务，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="清洗任务已登记", entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """保存清洗任务修改：必须带上读取时的版本号。

    版本对不上说明另一个窗口已经写过（例如班组刚确认完成），本次保存会被拦下；
    已确认完成或已取消的任务直接锁定，最后一次有效确认不会被旧会话回改。
    """
    entry, message = service.update_entry(entry_id, payload.values, payload.version)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条清洗任务执行安排清洗、开始清洗、确认完成；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
