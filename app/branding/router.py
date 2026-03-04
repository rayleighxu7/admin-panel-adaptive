from fastapi import APIRouter
from starlette.responses import Response

from app.config import settings

router = APIRouter()


def _safe_hex_color(value: str, fallback: str) -> str:
    h = value.lstrip("#")
    if len(h) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in h):
        return f"#{h.lower()}"
    return fallback


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in h):
        h = "206bc4"
    return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"


@router.get("/brand.css")
async def brand_css():
    p = _safe_hex_color(settings.BRAND_PRIMARY, "#206bc4")
    sidebar_bg = _safe_hex_color(settings.BRAND_SIDEBAR_BG, "#1b2434")
    sidebar_text = _safe_hex_color(settings.BRAND_SIDEBAR_TEXT, "#ffffff")
    accent = _safe_hex_color(settings.BRAND_ACCENT, p)
    danger = _safe_hex_color(settings.BRAND_DANGER, "#d63939")
    success = _safe_hex_color(settings.BRAND_SUCCESS, "#2fb344")
    css = f"""\
:root {{
    --brand-primary: {p};
    --brand-primary-rgb: {_hex_to_rgb(p)};
    --brand-sidebar-bg: {sidebar_bg};
    --brand-sidebar-text: {sidebar_text};
    --brand-accent: {accent};
    --brand-danger: {danger};
    --brand-success: {success};
    --tblr-primary: {p};
    --tblr-primary-rgb: {_hex_to_rgb(p)};
}}
"""
    return Response(content=css, media_type="text/css")
