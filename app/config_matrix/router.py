from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Customer, CustomerConfigMatrix, CustomConfig, PresetConfig
from app.preset_configs.router import ConfigSchema

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()
page_router = APIRouter()


@page_router.get("/config-matrix", include_in_schema=False)
async def config_matrix_page(request: Request):
    return templates.TemplateResponse(request=request, name="config_matrix.html")


class ConfigMatrixOut(BaseModel):
    id: int
    customer_id: str
    customer_name: str | None = None
    preset_config_id: int | None = None
    preset_config_name: str | None = None
    custom_config_id: int | None = None
    config: ConfigSchema | None = None
    effective_from: date
    created_at: datetime
    updated_at: datetime


class ConfigMatrixCreate(BaseModel):
    customer_id: str
    preset_config_id: int | None = None
    custom_config: ConfigSchema | None = None
    effective_from: date

    @model_validator(mode="after")
    def exactly_one_config(self):
        has_preset = self.preset_config_id is not None
        has_custom = self.custom_config is not None
        if has_preset == has_custom:
            raise ValueError("Provide exactly one of preset_config_id or custom_config")
        return self


class ConfigMatrixUpdate(BaseModel):
    preset_config_id: int | None = None
    custom_config: ConfigSchema | None = None
    effective_from: date | None = None


class ConfigMatrixListResponse(BaseModel):
    config_matrix: list[ConfigMatrixOut]
    total: int


def _active_query(db: Session):
    return (
        db.query(CustomerConfigMatrix)
        .options(
            joinedload(CustomerConfigMatrix.customer),
            joinedload(CustomerConfigMatrix.preset_config),
            joinedload(CustomerConfigMatrix.custom_config),
        )
        .filter(CustomerConfigMatrix.deleted_at.is_(None))
    )


def _resolve_config(m: CustomerConfigMatrix) -> ConfigSchema | None:
    if m.preset_config:
        return ConfigSchema(**m.preset_config.config)
    if m.custom_config:
        return ConfigSchema(**m.custom_config.config)
    return None


def _to_out(m: CustomerConfigMatrix) -> ConfigMatrixOut:
    return ConfigMatrixOut(
        id=m.id,
        customer_id=m.customer_id,
        customer_name=m.customer.name if m.customer else None,
        preset_config_id=m.preset_config_id,
        preset_config_name=m.preset_config.name if m.preset_config else None,
        custom_config_id=m.custom_config_id,
        config=_resolve_config(m),
        effective_from=m.effective_from,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


@router.get("", response_model=ConfigMatrixListResponse)
async def list_config_matrix(
    customer_id: str | None = Query(None, description="Filter by customer"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = _active_query(db)

    if customer_id:
        query = query.filter(CustomerConfigMatrix.customer_id == customer_id)

    total = query.count()
    rows = query.order_by(CustomerConfigMatrix.effective_from.desc()).offset(offset).limit(limit).all()

    return ConfigMatrixListResponse(
        config_matrix=[_to_out(m) for m in rows],
        total=total,
    )


@router.get("/{matrix_id}", response_model=ConfigMatrixOut)
async def get_config_matrix(matrix_id: int, db: Session = Depends(get_db)):
    m = _active_query(db).filter(CustomerConfigMatrix.id == matrix_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Config matrix entry not found")
    return _to_out(m)


@router.post("", response_model=ConfigMatrixOut, status_code=201)
async def create_config_matrix(body: ConfigMatrixCreate, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(
        Customer.id == body.customer_id, Customer.deleted_at.is_(None)
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    custom_config_id = None

    if body.preset_config_id:
        preset = db.query(PresetConfig).filter(
            PresetConfig.id == body.preset_config_id, PresetConfig.deleted_at.is_(None)
        ).first()
        if not preset:
            raise HTTPException(status_code=404, detail="Preset config not found")

    if body.custom_config:
        custom = CustomConfig(config=body.custom_config.model_dump())
        db.add(custom)
        db.flush()
        custom_config_id = custom.id

    entry = CustomerConfigMatrix(
        customer_id=body.customer_id,
        preset_config_id=body.preset_config_id,
        custom_config_id=custom_config_id,
        effective_from=body.effective_from,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    m = _active_query(db).filter(CustomerConfigMatrix.id == entry.id).first()
    return _to_out(m)


@router.patch("/{matrix_id}", response_model=ConfigMatrixOut)
async def update_config_matrix(
    matrix_id: int,
    body: ConfigMatrixUpdate,
    db: Session = Depends(get_db),
):
    m = _active_query(db).filter(CustomerConfigMatrix.id == matrix_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Config matrix entry not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "preset_config_id" in updates:
        if updates["preset_config_id"] is not None:
            preset = db.query(PresetConfig).filter(
                PresetConfig.id == updates["preset_config_id"], PresetConfig.deleted_at.is_(None)
            ).first()
            if not preset:
                raise HTTPException(status_code=404, detail="Preset config not found")
            m.preset_config_id = updates["preset_config_id"]
            m.custom_config_id = None

    if "custom_config" in updates and updates["custom_config"] is not None:
        if m.custom_config:
            m.custom_config.config = body.custom_config.model_dump()
        else:
            custom = CustomConfig(config=body.custom_config.model_dump())
            db.add(custom)
            db.flush()
            m.custom_config_id = custom.id
        m.preset_config_id = None

    if "effective_from" in updates:
        m.effective_from = updates["effective_from"]

    db.commit()
    db.refresh(m)

    m = _active_query(db).filter(CustomerConfigMatrix.id == matrix_id).first()
    return _to_out(m)


@router.delete("/{matrix_id}", status_code=204)
async def delete_config_matrix(matrix_id: int, db: Session = Depends(get_db)):
    m = (
        db.query(CustomerConfigMatrix)
        .filter(CustomerConfigMatrix.id == matrix_id, CustomerConfigMatrix.deleted_at.is_(None))
        .first()
    )
    if not m:
        raise HTTPException(status_code=404, detail="Config matrix entry not found")

    m.deleted_at = datetime.utcnow()
    m.deleted_by = "api"
    db.commit()
