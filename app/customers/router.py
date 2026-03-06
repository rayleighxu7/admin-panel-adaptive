from datetime import date, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common import mark_soft_deleted
from app.database import get_db
from app.models import AuditLog, Customer, CustomerConfigMatrix, CustomerNote

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()
page_router = APIRouter()


@page_router.get("/customers", include_in_schema=False)
async def customers_page(request: Request):
    return templates.TemplateResponse(request=request, name="customers.html")


@page_router.get("/customers/{customer_id}", include_in_schema=False)
async def customer_detail_page(request: Request, customer_id: str):
    return templates.TemplateResponse(request=request, name="customer_detail.html", context={"customer_id": customer_id})


class CustomerOut(BaseModel):
    id: str
    name: str
    email: str
    phone: str | None = None
    address: str | None = None
    date_of_birth: date | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerCreate(BaseModel):
    id: Annotated[str, Field(min_length=1, max_length=36)] | None = None
    name: Annotated[str, Field(min_length=1, max_length=100)]
    email: EmailStr
    phone: Annotated[str, Field(max_length=30)] | None = None
    address: Annotated[str, Field(max_length=1000)] | None = None
    date_of_birth: date | None = None


class CustomerUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    email: EmailStr | None = None
    phone: Annotated[str, Field(max_length=30)] | None = None
    address: Annotated[str, Field(max_length=1000)] | None = None
    date_of_birth: date | None = None


class CustomerListResponse(BaseModel):
    customers: list[CustomerOut]
    total: int


class CustomerTimelineItem(BaseModel):
    event_time: datetime
    event_type: str
    title: str
    detail: str | None = None


class CustomerTimelineResponse(BaseModel):
    entries: list[CustomerTimelineItem]


def _active_query(db: Session):
    return db.query(Customer).filter(Customer.deleted_at.is_(None))


@router.get("", response_model=CustomerListResponse)
def list_customers(
    search: str | None = Query(None, description="Search by name or email"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = _active_query(db)

    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            Customer.name.ilike(pattern),
            Customer.email.ilike(pattern),
        ))

    total = query.count()
    customers = query.order_by(Customer.created_at.desc()).offset(offset).limit(limit).all()

    return CustomerListResponse(
        customers=[CustomerOut.model_validate(c) for c in customers],
        total=total,
    )


@router.get("/{customer_id}/timeline", response_model=CustomerTimelineResponse)
def customer_timeline(
    customer_id: str,
    limit: int = Query(80, ge=1, le=200),
    db: Session = Depends(get_db),
):
    _get = _active_query(db).filter(Customer.id == customer_id).first()
    if not _get:
        raise HTTPException(status_code=404, detail="Customer not found")

    notes = (
        db.query(CustomerNote)
        .filter(
            CustomerNote.customer_id == customer_id,
            CustomerNote.deleted_at.is_(None),
        )
        .order_by(CustomerNote.created_at.desc())
        .limit(limit)
        .all()
    )
    assignments = (
        db.query(CustomerConfigMatrix)
        .filter(
            CustomerConfigMatrix.customer_id == customer_id,
            CustomerConfigMatrix.deleted_at.is_(None),
        )
        .order_by(CustomerConfigMatrix.created_at.desc())
        .limit(limit)
        .all()
    )
    audit_rows_raw = (
        db.query(AuditLog)
        .filter(
            or_(
                AuditLog.endpoint.ilike("/api/customers%"),
                AuditLog.endpoint.ilike("/api/config-matrix%"),
            )
        )
        .order_by(AuditLog.event_time_utc.desc())
        .limit(limit * 4)
        .all()
    )
    audit_rows = []
    for row in audit_rows_raw:
        path_customer = str((row.path_params or {}).get("customer_id", ""))
        body_customer = str((row.request_body or {}).get("customer_id", ""))
        endpoint_hit = f"/api/customers/{customer_id}" in (row.endpoint or "")
        if path_customer == customer_id or body_customer == customer_id or endpoint_hit:
            audit_rows.append(row)

    entries: list[CustomerTimelineItem] = []
    for n in notes:
        entries.append(
            CustomerTimelineItem(
                event_time=n.created_at,
                event_type="note",
                title="Customer note added",
                detail=(n.note[:180] + "...") if len(n.note) > 180 else n.note,
            )
        )
    for m in assignments:
        config_type = "Preset config" if m.preset_config_id else "Custom config"
        config_id = str(m.preset_config_id or m.custom_config_id or "")
        entries.append(
            CustomerTimelineItem(
                event_time=m.created_at,
                event_type="assignment",
                title=f"{config_type} assignment created",
                detail=f"Config #{config_id} effective from {m.effective_from.isoformat()}",
            )
        )
    for row in audit_rows[:limit]:
        entries.append(
            CustomerTimelineItem(
                event_time=row.event_time_utc,
                event_type="audit",
                title=f"{row.method} {row.endpoint}",
                detail=f"Status {row.response_status_code}",
            )
        )

    entries.sort(key=lambda item: item.event_time, reverse=True)
    return CustomerTimelineResponse(entries=entries[:limit])


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    customer = _active_query(db).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerOut.model_validate(customer)


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(body: CustomerCreate, db: Session = Depends(get_db)):
    kwargs = {"name": body.name, "email": body.email}
    if body.id:
        kwargs["id"] = body.id
    if body.phone is not None:
        kwargs["phone"] = body.phone
    if body.address is not None:
        kwargs["address"] = body.address
    if body.date_of_birth is not None:
        kwargs["date_of_birth"] = body.date_of_birth
    customer = Customer(**kwargs)
    db.add(customer)
    try:
        db.commit()
        db.refresh(customer)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Customer id or email already exists")
    return CustomerOut.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: str,
    body: CustomerUpdate,
    db: Session = Depends(get_db),
):
    customer = _active_query(db).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "id" in updates:
        raise HTTPException(status_code=400, detail="Customer ID cannot be changed")

    for field, value in updates.items():
        setattr(customer, field, value)

    try:
        db.commit()
        db.refresh(customer)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Customer email already exists")
    return CustomerOut.model_validate(customer)


@router.delete("/{customer_id}", status_code=204)
def delete_customer(
    customer_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    customer = _active_query(db).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    mark_soft_deleted(customer, request)
    db.commit()
