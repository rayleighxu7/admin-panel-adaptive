from fastapi import APIRouter
from starlette.responses import Response

from app.config import settings

router = APIRouter()


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"


@router.get("/brand.css")
async def brand_css():
    p = settings.BRAND_PRIMARY
    css = f"""\
:root {{
    --brand-primary: {p};
    --brand-primary-rgb: {_hex_to_rgb(p)};
    --brand-sidebar-bg: {settings.BRAND_SIDEBAR_BG};
    --brand-sidebar-text: {settings.BRAND_SIDEBAR_TEXT};
    --brand-accent: {settings.BRAND_ACCENT};
    --brand-danger: {settings.BRAND_DANGER};
    --brand-success: {settings.BRAND_SUCCESS};
    --tblr-primary: {p};
    --tblr-primary-rgb: {_hex_to_rgb(p)};
}}
"""
    return Response(content=css, media_type="text/css")
