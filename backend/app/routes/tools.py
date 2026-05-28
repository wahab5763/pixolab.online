"""
Free image utility tools — no auth required.
  POST /api/tools/remove-background
  POST /api/tools/change-background
"""
import io
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from PIL import Image

from ..config import get_settings
from ..services import (
    _fit_cover,
    _finalize_output,
    _try_remove_background,
    generate_hf_background,
    _rembg_session,
)

router = APIRouter(prefix="/tools", tags=["tools"])
settings = get_settings()
ALLOWED = {"image/jpeg", "image/png", "image/webp"}


def _read_pil(upload: UploadFile, label: str = "image", max_mb: int = 15) -> Image.Image:
    if upload.content_type not in ALLOWED:
        raise HTTPException(400, f"{label} must be PNG, JPG or WEBP")
    data = upload.file.read()
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(413, f"{label} too large – max {max_mb} MB")
    try:
        return Image.open(io.BytesIO(data))
    except Exception:
        raise HTTPException(400, f"Could not open {label}")


def _pil_to_stream(img: Image.Image, fmt: str = "PNG") -> StreamingResponse:
    buf = io.BytesIO()
    if fmt == "PNG":
        img.save(buf, format="PNG", optimize=True)
    else:
        img.convert("RGB").save(buf, format="JPEG", quality=92, optimize=True)
    buf.seek(0)
    mime = "image/png" if fmt == "PNG" else "image/jpeg"
    ext = "png" if fmt == "PNG" else "jpg"
    return StreamingResponse(
        buf, media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="result.{ext}"'},
    )


@router.post("/remove-background")
def remove_background(image: UploadFile = File(...)):
    """Remove background — FREE, no auth required."""
    img = _read_pil(image)
    try:
        result = _try_remove_background(img, kind="product")
        import gc
        _rembg_session.cache_clear()
        gc.collect()
        return _pil_to_stream(result, "PNG")
    except Exception as exc:
        raise HTTPException(500, f"Background removal failed: {exc}")


@router.post("/change-background")
def change_background(
    subject_image: UploadFile = File(...),
    background_image: Optional[UploadFile] = File(None),
    bg_color: str = Form("#0d0d1a"),
    bg_prompt: str = Form(""),
    use_ai: bool = Form(False),
):
    """Composite subject onto a new background — FREE, no auth required."""
    subj_img = _read_pil(subject_image, "subject")
    if settings.enable_background_removal:
        subj_cut = _try_remove_background(subj_img, kind="person")
        import gc
        _rembg_session.cache_clear()
        gc.collect()
    else:
        subj_cut = subj_img.convert("RGBA")

    w, h = subj_cut.size

    if background_image and background_image.filename:
        bg_pil = _read_pil(background_image, "background")
        bg = _fit_cover(bg_pil, (w, h)).convert("RGBA")
    elif use_ai and bg_prompt.strip() and settings.enable_hf_background:
        bg_pil = generate_hf_background(bg_prompt.strip(), w, h)
        if bg_pil is None:
            raise HTTPException(503, "AI background generation failed. Try a manual background.")
        bg = bg_pil.convert("RGBA")
    else:
        hex_c = bg_color.strip().lstrip("#")
        try:
            r, g, b = int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16)
        except Exception:
            r, g, b = 13, 13, 26
        bg = Image.new("RGBA", (w, h), (r, g, b, 255))

    canvas = bg.copy()
    canvas.alpha_composite(subj_cut)
    return _pil_to_stream(_finalize_output(canvas.convert("RGB")), "JPEG")
