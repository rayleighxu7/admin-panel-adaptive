from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CustomerConfigMatrix, PresetConfig

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()
page_router = APIRouter()


@page_router.get("/preset-configs", include_in_schema=False)
async def preset_configs_page(request: Request):
    return templates.TemplateResponse(request=request, name="preset_configs.html")


@page_router.get("/preset-configs/{preset_id}", include_in_schema=False)
async def preset_config_detail_page(request: Request, preset_id: int):
    return templates.TemplateResponse(request=request, name="preset_config_detail.html", context={"preset_id": preset_id})


class PerOrderConfig(BaseModel):
    fee_cents: int = 0
    quantity_threshold: int = 0


class ConfigSchema(BaseModel):
    commission_percentage: float = Field(0, ge=0, le=1)
    affiliate_percentage: float = Field(0, ge=0, le=1)
    gmv_percentage: float = Field(0, ge=0, le=1)
    per_order: PerOrderConfig = PerOrderConfig()
    flat_fee_cents: int = Field(0, ge=0)


class PresetConfigOut(BaseModel):
    id: int
    name: str
    config: ConfigSchema
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PresetConfigCreate(BaseModel):
    name: str
    config: ConfigSchema


class PresetConfigUpdate(BaseModel):
    name: str | None = None
    config: ConfigSchema | None = None


class PresetConfigListResponse(BaseModel):
    preset_configs: list[PresetConfigOut]
    total: int


def _active_query(db: Session):
    return db.query(PresetConfig).filter(PresetConfig.deleted_at.is_(None))


@router.get("", response_model=PresetConfigListResponse)
async def list_preset_configs(
    search: str | None = Query(None, description="Search by name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = _active_query(db)

    if search:
        query = query.filter(PresetConfig.name.ilike(f"%{search}%"))

    total = query.count()
    presets = query.order_by(PresetConfig.name).offset(offset).limit(limit).all()

    return PresetConfigListResponse(
        preset_configs=[PresetConfigOut.model_validate(p) for p in presets],
        total=total,
    )


@router.get("/{preset_id}", response_model=PresetConfigOut)
async def get_preset_config(preset_id: int, db: Session = Depends(get_db)):
    preset = _active_query(db).filter(PresetConfig.id == preset_id).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset config not found")
    return PresetConfigOut.model_validate(preset)


@router.post("", response_model=PresetConfigOut, status_code=201)
async def create_preset_config(body: PresetConfigCreate, db: Session = Depends(get_db)):
    preset = PresetConfig(name=body.name, config=body.config.model_dump())
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return PresetConfigOut.model_validate(preset)


@router.patch("/{preset_id}", response_model=PresetConfigOut)
async def update_preset_config(
    preset_id: int,
    body: PresetConfigUpdate,
    db: Session = Depends(get_db),
):
    preset = _active_query(db).filter(PresetConfig.id == preset_id).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset config not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "config" in updates:
        updates["config"] = body.config.model_dump()

    for field, value in updates.items():
        setattr(preset, field, value)

    db.commit()
    db.refresh(preset)
    return PresetConfigOut.model_validate(preset)


@router.delete("/{preset_id}", status_code=204)
async def delete_preset_config(preset_id: int, db: Session = Depends(get_db)):
    preset = _active_query(db).filter(PresetConfig.id == preset_id).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset config not found")

    linked = db.query(CustomerConfigMatrix).filter(
        CustomerConfigMatrix.preset_config_id == preset_id,
        CustomerConfigMatrix.deleted_at.is_(None),
    ).count()
    if linked:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: preset is linked to {linked} customer{'s' if linked != 1 else ''}",
        )

    preset.deleted_at = datetime.utcnow()
    preset.deleted_by = "api"
    db.commit()
