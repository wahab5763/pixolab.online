import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import get_settings
from ..services import STYLE_DIMENSIONS, SUPPORTED_MODES, compose_ad, compose_from_template
from ..templates_config import TEMPLATES, TEMPLATE_MAP

router = APIRouter(prefix="/generation", tags=["generation"])
settings = get_settings()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _save_upload(upload: UploadFile, prefix: str) -> Path:
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"{prefix} must be PNG, JPG, or WEBP")
    suffix = Path(upload.filename or "image.png").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".png"
    out_path = settings.storage_dir / "uploads" / f"{prefix}_{uuid.uuid4().hex}{suffix}"
    size = 0
    with out_path.open("wb") as buffer:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > settings.max_upload_mb * 1024 * 1024:
                out_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"File too large. Max {settings.max_upload_mb}MB")
            buffer.write(chunk)
    return out_path


@router.get("/styles")
def styles():
    return [
        {"id": "instagram_ad", "label": "Instagram Ad", "dimensions": STYLE_DIMENSIONS["instagram_ad"]},
        {"id": "linkedin_post", "label": "LinkedIn Promo", "dimensions": STYLE_DIMENSIONS["linkedin_post"]},
        {"id": "product_poster", "label": "Product Launch Poster", "dimensions": STYLE_DIMENSIONS["product_poster"]},
        {"id": "brand_ambassador", "label": "Brand Ambassador", "dimensions": STYLE_DIMENSIONS["brand_ambassador"]},
        {"id": "youtube_thumbnail", "label": "YouTube Thumbnail", "dimensions": STYLE_DIMENSIONS["youtube_thumbnail"]},
    ]


@router.post("/generate")
def generate(
    person_image: UploadFile = File(...),
    product_image: UploadFile = File(...),
    style: str = Form("instagram_ad"),
    mode: str = Form("poster"),
    brand_name: str = Form(""),
    headline: str = Form(""),
    subheadline: str = Form(""),
    cta: str = Form(""),
    person_caption: str = Form("Brand influencer"),
    product_caption: str = Form("Premium product"),
    target_audience: str = Form("18-35 years old"),
    consent_confirmed: bool = Form(False),
):
    if not consent_confirmed:
        raise HTTPException(status_code=400, detail="You must confirm rights/consent to use the images")
    if style not in STYLE_DIMENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported style")
    if mode not in SUPPORTED_MODES:
        raise HTTPException(status_code=400, detail="Unsupported generation mode")

    person_path = _save_upload(person_image, "person")
    product_path = _save_upload(product_image, "product")

    try:
        result_path, meta = compose_ad(
            person_path=person_path,
            product_path=product_path,
            style=style,
            brand_name=brand_name.strip(),
            headline=headline.strip(),
            subheadline=subheadline.strip(),
            cta=cta.strip(),
            mode=mode,
            plan="free",
            person_caption=person_caption.strip(),
            product_caption=product_caption.strip(),
            target_audience=target_audience.strip(),
        )
    except Exception as exc:
        person_path.unlink(missing_ok=True)
        product_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Image generation failed: {exc}")

    rel_url = f"/static/results/{result_path.name}"
    full_url = f"{settings.backend_url}{rel_url}"

    return {
        "result_url": full_url,
        "width": meta.get("width", 1080),
        "height": meta.get("height", 1080),
        "style": style,
        "mode": mode,
    }


@router.get("/templates")
def list_templates():
    return TEMPLATES


@router.post("/generate-template")
def generate_template(
    product_image: UploadFile = File(...),
    person_image: Optional[UploadFile] = File(None),
    template_id: str = Form(...),
    brand_name: str = Form(""),
    headline: str = Form(""),
    subheadline: str = Form(""),
    cta: str = Form(""),
    feature1: str = Form(""),
    feature2: str = Form(""),
    feature3: str = Form(""),
    benefit1: str = Form(""),
    benefit2: str = Form(""),
    bottom_tagline: str = Form(""),
    consent_confirmed: bool = Form(False),
):
    if not consent_confirmed:
        raise HTTPException(status_code=400, detail="You must confirm rights/consent to use the uploaded images")
    if template_id not in TEMPLATE_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown template: {template_id}")

    product_path = _save_upload(product_image, "product")
    person_path: Optional[Path] = None
    if person_image and person_image.filename and person_image.size:
        try:
            person_path = _save_upload(person_image, "person")
        except Exception:
            person_path = None

    template_data = {
        "brand_name": brand_name.strip(),
        "headline": headline.strip(),
        "subheadline": subheadline.strip(),
        "cta": cta.strip(),
        "feature1": feature1.strip(),
        "feature2": feature2.strip(),
        "feature3": feature3.strip(),
        "benefit1": benefit1.strip(),
        "benefit2": benefit2.strip(),
        "bottom_tagline": bottom_tagline.strip(),
    }

    try:
        result_path, meta = compose_from_template(
            person_path=person_path,
            product_path=product_path,
            template_id=template_id,
            template_data=template_data,
            plan="free",
        )
    except Exception as exc:
        product_path.unlink(missing_ok=True)
        if person_path:
            person_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Template generation failed: {exc}")

    tmpl = TEMPLATE_MAP[template_id]
    rel_url = f"/static/results/{result_path.name}"
    full_url = f"{settings.backend_url}{rel_url}"

    return {
        "result_url": full_url,
        "width": meta.get("width", 1080),
        "height": meta.get("height", 1080),
        "style": tmpl["style"],
        "mode": f"template:{template_id}",
    }
