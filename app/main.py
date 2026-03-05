from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth_router import router as auth_router
from app.branding import router as branding_router
from app.config import settings
from app.config_matrix import page_router as matrix_page_router, router as config_matrix_router
from app.customer_notes import router as customer_notes_router
from app.customers import page_router as customers_page_router, router as customers_router
from app.database import create_engine, dispose_engine, get_session_factory
from app.db_schema import router as schema_router
from app.models import AdminUser, AuditLog
from app.preset_configs import page_router as presets_page_router, router as preset_configs_router

BASE_DIR = Path(__file__).resolve().parent.parent

create_engine()

AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
AUDIT_BODY_LIMIT_BYTES = 20_000


def _truncate_text(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    return f"{value[:max_len]}...[truncated]"


def _safe_json_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _safe_json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_json_value(v) for v in value]
    return str(value)


def _sanitize_payload(value):
    sensitive_keys = {"password", "password_hash", "secret", "token", "api_key"}
    if isinstance(value, dict):
        sanitized = {}
        for key, raw in value.items():
            key_l = str(key).lower()
            if key_l in sensitive_keys:
                sanitized[str(key)] = "***redacted***"
            else:
                sanitized[str(key)] = _sanitize_payload(raw)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload(v) for v in value]
    return _safe_json_value(value)


async def _parse_request_body(request: Request) -> dict:
    content_type = (request.headers.get("content-type") or "").lower()
    body_bytes = await request.body()
    if not body_bytes:
        return {}

    if len(body_bytes) > AUDIT_BODY_LIMIT_BYTES:
        return {
            "_truncated": True,
            "_note": f"Body exceeds {AUDIT_BODY_LIMIT_BYTES} bytes; omitted from audit log",
        }

    if "application/json" in content_type:
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
            return _sanitize_payload(payload) if isinstance(payload, (dict, list)) else {"value": _safe_json_value(payload)}
        except Exception:
            return {"_raw": _truncate_text(body_bytes.decode("utf-8", errors="replace"), 2000)}

    if "application/x-www-form-urlencoded" in content_type:
        parsed = parse_qs(body_bytes.decode("utf-8", errors="replace"), keep_blank_values=True)
        normalized = {k: v if len(v) != 1 else v[0] for k, v in parsed.items()}
        return _sanitize_payload(normalized)

    return {
        "_content_type": content_type or "unknown",
        "_raw": _truncate_text(body_bytes.decode("utf-8", errors="replace"), 2000),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    dispose_engine()


app = FastAPI(title="Adaptive Admin Panel", debug=settings.DEBUG, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "statics")), name="static")

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()
        is_static = path.startswith("/static/")
        is_brand_css = path == "/brand.css"
        is_login = path == "/login"
        is_logout = path == "/logout"
        is_audit_path = path.startswith("/api/audit-log")
        is_reference_path = (
            path in {"/schema", "/api/schema", "/openapi.json", "/redoc"}
            or path.startswith("/docs")
        )
        should_audit = (
            method in AUDITED_METHODS
            and not is_static
            and not is_brand_css
            and not is_login
            and not is_logout
            and not is_audit_path
        )
        request_body = {}
        if should_audit:
            request_body = await _parse_request_body(request)

        if settings.ENABLE_AUTH and not (is_static or is_brand_css or is_login or is_logout):
            user_id = request.session.get("admin_user_id")
            if not user_id:
                if path.startswith("/api/"):
                    return PlainTextResponse("Authentication required", status_code=401)
                return RedirectResponse(
                    url=f"/login?next={request.url.path}",
                    status_code=303,
                )

            session_factory = get_session_factory()
            with session_factory() as db:
                user = (
                    db.query(AdminUser)
                    .filter(AdminUser.id == user_id, AdminUser.is_active.is_(True))
                    .first()
                )
            if user is None:
                request.session.clear()
                if path.startswith("/api/"):
                    return PlainTextResponse("Authentication required", status_code=401)
                return RedirectResponse(url="/login", status_code=303)

            request.state.admin_user_id = user.id
            request.state.admin_username = user.username

            if is_reference_path and user.username != "admin":
                if path.startswith("/api/") or path == "/openapi.json":
                    return PlainTextResponse("Forbidden", status_code=403)
                return RedirectResponse(url="/customers", status_code=303)

        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin:
                expected_origin = str(request.base_url).rstrip("/")
                if origin.rstrip("/") != expected_origin:
                    return PlainTextResponse("Blocked by origin policy", status_code=403)

        response = None
        audit_error = None
        try:
            response = await call_next(request)
        except Exception as exc:
            audit_error = str(exc)
            raise
        finally:
            if should_audit:
                try:
                    session_factory = get_session_factory()
                    query_params = {}
                    for key in request.query_params.keys():
                        values = request.query_params.getlist(key)
                        query_params[key] = values[0] if len(values) == 1 else values
                    path_params = {
                        k: _safe_json_value(v)
                        for k, v in request.path_params.items()
                    }
                    audit_row = AuditLog(
                        event_time_utc=datetime.now(timezone.utc),
                        method=method,
                        endpoint=path,
                        query_params=_sanitize_payload(query_params),
                        path_params=_sanitize_payload(path_params),
                        request_body=_sanitize_payload(request_body),
                        response_status_code=response.status_code if response is not None else 500,
                        admin_user_id=getattr(request.state, "admin_user_id", None),
                        admin_username=getattr(request.state, "admin_username", None),
                        client_ip=request.client.host if request.client else None,
                        user_agent=_truncate_text(request.headers.get("user-agent", ""), 512) or None,
                        error=_truncate_text(audit_error, 1000) if audit_error else None,
                    )
                    with session_factory() as db:
                        db.add(audit_row)
                        db.commit()
                except Exception:
                    # Never block application flow due to audit logging failures.
                    pass

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE_NAME,
    max_age=settings.SESSION_MAX_AGE_SECONDS,
    https_only=settings.SESSION_HTTPS_ONLY,
)

app.include_router(auth_router)
app.include_router(branding_router)
app.include_router(customers_page_router)
app.include_router(presets_page_router)
app.include_router(matrix_page_router)
app.include_router(customers_router, prefix="/api/customers", tags=["customers"])
app.include_router(customer_notes_router, prefix="/api/customers", tags=["customer-notes"])
app.include_router(preset_configs_router, prefix="/api/preset-configs", tags=["preset-configs"])
app.include_router(config_matrix_router, prefix="/api/config-matrix", tags=["config-matrix"])
app.include_router(schema_router, tags=["schema"])


@app.get("/")
async def root():
    return RedirectResponse(url="/customers")
