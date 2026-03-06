from datetime import datetime, timezone

from fastapi import Request


def current_actor(request: Request) -> str:
    return (
        getattr(request.state, "admin_username", None)
        or request.session.get("admin_username")
        or "system"
    )


def mark_soft_deleted(entity: object, request: Request) -> None:
    setattr(entity, "deleted_at", datetime.now(timezone.utc))
    setattr(entity, "deleted_by", current_actor(request))
