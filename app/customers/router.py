from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer

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
    id: str | None = None
    name: str
    email: EmailStr
    phone: str | None = None
    address: str | None = None
    date_of_birth: date | None = None


class CustomerUpdate(BaseModel):
    id: str | None = None
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    date_of_birth: date | None = None


class CustomerListResponse(BaseModel):
    customers: list[CustomerOut]
    total: int


def _active_query(db: Session):
    return db.query(Customer).filter(Customer.deleted_at.is_(None))


@router.get("", response_model=CustomerListResponse)
async def list_customers(
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


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(customer_id: str, db: Session = Depends(get_db)):
    customer = _active_query(db).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerOut.model_validate(customer)


@router.post("", response_model=CustomerOut, status_code=201)
async def create_customer(body: CustomerCreate, db: Session = Depends(get_db)):
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
    db.commit()
    db.refresh(customer)
    return CustomerOut.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerOut)
async def update_customer(
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

    for field, value in updates.items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    return CustomerOut.model_validate(customer)


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(customer_id: str, db: Session = Depends(get_db)):
    customer = _active_query(db).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer.deleted_at = datetime.utcnow()
    customer.deleted_by = "api"
    db.commit()
