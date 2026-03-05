from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import authenticate_admin, is_safe_next_path
from app.database import get_db
from app.models import AdminUser

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/login", include_in_schema=False)
async def login_page(request: Request, next: str | None = None):
    if request.session.get("admin_user_id"):
        target = next if is_safe_next_path(next) else "/customers"
        return RedirectResponse(url=target, status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None, "next": next or ""},
    )


@router.post("/login", include_in_schema=False)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(default=""),
    db: Session = Depends(get_db),
):
    admin_user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if not authenticate_admin(username=username, password=password, admin_user=admin_user):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Invalid username or password.", "next": next},
            status_code=401,
        )

    request.session["admin_user_id"] = admin_user.id
    request.session["admin_username"] = admin_user.username
    target = next if is_safe_next_path(next) else "/customers"
    return RedirectResponse(url=target, status_code=303)


@router.get("/logout", include_in_schema=False)
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
