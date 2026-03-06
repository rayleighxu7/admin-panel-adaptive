from http import HTTPStatus
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditLog

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()
page_router = APIRouter()

_ACTION_BY_METHOD: dict[str, str] = {
    "POST": "Created",
    "PUT": "Updated",
    "PATCH": "Updated",
    "DELETE": "Deleted",
}


class AuditLogOut(BaseModel):
    id: int
    event_time_utc: str
    method: str
    endpoint: str
    response_status_code: int
    response_status_label: str
    admin_username: str | None = None
    operation_summary: str
    detail_summary: str | None = None
    status_tone: str
    has_error: bool


class AuditLogListResponse(BaseModel):
    entries: list[AuditLogOut]
    total: int


def _humanize_segment(value: str) -> str:
    return value.replace("-", " ").replace("_", " ").strip().title()


def _target_from_endpoint(endpoint: str) -> str:
    parts = [part for part in endpoint.strip("/").split("/") if part]
    if parts and parts[0] == "api":
        parts = parts[1:]
    if not parts:
        return "System"

    root = parts[0]
    if root == "customers":
        if len(parts) >= 3 and parts[2] == "notes":
            return "Customer Notes"
        return "Customers"
    if root == "preset-configs":
        return "Preset Configs"
    if root == "config-matrix":
        return "Config Matrix"
    return _humanize_segment(root)


def _entity_hint(row: AuditLog) -> str | None:
    path_params: dict[str, Any] = row.path_params or {}
    for key in ("customer_id", "note_id", "preset_id", "matrix_id", "id"):
        value = path_params.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _payload_summary(payload: dict[str, Any]) -> str | None:
    if not payload:
        return None
    if payload.get("_truncated"):
        return "Request payload omitted due to size limit"

    keys = [str(k) for k in payload.keys() if not str(k).startswith("_")]
    if not keys:
        return None

    keys_sorted = sorted(keys)
    if len(keys_sorted) > 5:
        return f"Fields: {', '.join(keys_sorted[:5])}, ..."
    return f"Fields: {', '.join(keys_sorted)}"


def _status_label(code: int) -> str:
    try:
        return HTTPStatus(code).phrase
    except ValueError:
        return "Unknown"


def _status_tone(code: int) -> str:
    if code >= 500:
        return "danger"
    if code >= 400:
        return "warning"
    return "success"


def _summaries(row: AuditLog) -> tuple[str, str | None]:
    action = _ACTION_BY_METHOD.get((row.method or "").upper(), "Changed")
    target = _target_from_endpoint(row.endpoint or "")
    operation_summary = f"{action} {target}"

    detail_parts: list[str] = []
    entity = _entity_hint(row)
    if entity:
        detail_parts.append(f"Target ID: {entity}")

    if row.query_params:
        query_keys = sorted(str(k) for k in row.query_params.keys())
        if query_keys:
            detail_parts.append(f"Query: {', '.join(query_keys[:4])}{', ...' if len(query_keys) > 4 else ''}")

    payload_detail = _payload_summary(row.request_body or {})
    if payload_detail:
        detail_parts.append(payload_detail)

    if row.error:
        detail_parts.append("Runtime error captured")

    return operation_summary, " | ".join(detail_parts) if detail_parts else None


@page_router.get("/audit-log", include_in_schema=False)
async def audit_log_page(request: Request):
    return templates.TemplateResponse(request=request, name="audit_log.html")


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    method: str | None = Query(None, description="Filter by HTTP method"),
    actor: str | None = Query(None, description="Filter by admin username"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)

    if method:
        query = query.filter(AuditLog.method == method.upper().strip())
    if actor:
        query = query.filter(AuditLog.admin_username.ilike(f"%{actor.strip()}%"))

    total = query.count()
    rows = query.order_by(AuditLog.event_time_utc.desc()).offset(offset).limit(limit).all()

    entries: list[AuditLogOut] = []
    for row in rows:
        operation_summary, detail_summary = _summaries(row)
        entries.append(
            AuditLogOut(
                id=row.id,
                event_time_utc=row.event_time_utc.isoformat(),
                method=row.method,
                endpoint=row.endpoint,
                response_status_code=row.response_status_code,
                response_status_label=_status_label(row.response_status_code),
                admin_username=row.admin_username,
                operation_summary=operation_summary,
                detail_summary=detail_summary,
                status_tone=_status_tone(row.response_status_code),
                has_error=bool(row.error),
            )
        )

    return AuditLogListResponse(entries=entries, total=total)
