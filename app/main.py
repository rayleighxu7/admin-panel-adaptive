from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

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
