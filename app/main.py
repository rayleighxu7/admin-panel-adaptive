from contextlib import asynccontextmanager
from pathlib import Path
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.branding import router as branding_router
from app.config import settings
from app.config_matrix import page_router as matrix_page_router, router as config_matrix_router
from app.customer_notes import router as customer_notes_router
from app.customers import page_router as customers_page_router, router as customers_router
from app.database import create_engine, dispose_engine
from app.db_schema import router as schema_router
from app.preset_configs import page_router as presets_page_router, router as preset_configs_router

BASE_DIR = Path(__file__).resolve().parent.parent

create_engine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    dispose_engine()


app = FastAPI(title="Adaptive Admin Panel", debug=settings.DEBUG, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "statics")), name="static")

if settings.ENABLE_AUTH:
    weak_user = settings.ADMIN_USERNAME.strip().lower() in {"", "admin"}
    weak_pass = settings.ADMIN_PASSWORD.strip().lower() in {"", "changeme", "change-me", "change-me-now", "password"}
    if weak_user and weak_pass:
        raise RuntimeError(
            "Refusing to start with default admin credentials. "
            "Set ADMIN_USERNAME and ADMIN_PASSWORD in your environment."
        )


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        is_static = path.startswith("/static/")
        is_brand_css = path == "/brand.css"

        if settings.ENABLE_AUTH and not (is_static or is_brand_css):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Basic "):
                return PlainTextResponse(
                    "Authentication required",
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Admin Panel"'},
                )
            try:
                import base64

                decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
                username, password = decoded.split(":", 1)
            except Exception:
                return PlainTextResponse("Invalid authentication", status_code=401)

            valid_user = secrets.compare_digest(username, settings.ADMIN_USERNAME)
            valid_pass = secrets.compare_digest(password, settings.ADMIN_PASSWORD)
            if not (valid_user and valid_pass):
                return PlainTextResponse(
                    "Invalid credentials",
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Admin Panel"'},
                )

        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin:
                expected_origin = str(request.base_url).rstrip("/")
                if origin.rstrip("/") != expected_origin:
                    return PlainTextResponse("Blocked by origin policy", status_code=403)

        response = await call_next(request)
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
