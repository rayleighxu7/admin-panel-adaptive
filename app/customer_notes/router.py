from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer, CustomerNote

router = APIRouter()


class NoteOut(BaseModel):
    id: int
    customer_id: str
    note: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NoteCreate(BaseModel):
    note: str


class NoteUpdate(BaseModel):
    note: str


class NoteListResponse(BaseModel):
    notes: list[NoteOut]
    total: int


def _active_query(db: Session, customer_id: str):
    return db.query(CustomerNote).filter(
        CustomerNote.customer_id == customer_id,
        CustomerNote.deleted_at.is_(None),
    )


def _get_customer_or_404(db: Session, customer_id: str) -> Customer:
    customer = db.query(Customer).filter(
        Customer.id == customer_id, Customer.deleted_at.is_(None)
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/{customer_id}/notes", response_model=NoteListResponse)
async def list_notes(
    customer_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    _get_customer_or_404(db, customer_id)
    query = _active_query(db, customer_id)
    total = query.count()
    notes = query.order_by(CustomerNote.created_at.desc()).offset(offset).limit(limit).all()

    return NoteListResponse(
        notes=[NoteOut.model_validate(n) for n in notes],
        total=total,
    )


@router.post("/{customer_id}/notes", response_model=NoteOut, status_code=201)
async def create_note(
    customer_id: str,
    body: NoteCreate,
    db: Session = Depends(get_db),
):
    _get_customer_or_404(db, customer_id)
    note = CustomerNote(customer_id=customer_id, note=body.note)
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteOut.model_validate(note)


@router.patch("/{customer_id}/notes/{note_id}", response_model=NoteOut)
async def update_note(
    customer_id: str,
    note_id: int,
    body: NoteUpdate,
    db: Session = Depends(get_db),
):
    note = _active_query(db, customer_id).filter(CustomerNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    note.note = body.note
    db.commit()
    db.refresh(note)
    return NoteOut.model_validate(note)


@router.delete("/{customer_id}/notes/{note_id}", status_code=204)
async def delete_note(
    customer_id: str,
    note_id: int,
    db: Session = Depends(get_db),
):
    note = _active_query(db, customer_id).filter(CustomerNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    note.deleted_at = datetime.utcnow()
    note.deleted_by = "api"
    db.commit()
