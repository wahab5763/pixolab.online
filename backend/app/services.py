from __future__ import annotations

import concurrent.futures
import json
import logging
import math
import random
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .config import get_settings
from . import background_removal
from . import groq_client as groq_module
from . import inpainting

logger = logging.getLogger(__name__)

settings = get_settings()

STYLE_DIMENSIONS = {
    "instagram_ad": (1080, 1080),
    "linkedin_post": (1200, 627),
    "product_poster": (1080, 1350),
    "brand_ambassador": (1080, 1350),
    "youtube_thumbnail": (1280, 720),
}

STYLE_LABELS = {
    "instagram_ad": "Instagram Ad",
    "linkedin_post": "LinkedIn Promo",
    "product_poster": "Product Launch",
    "brand_ambassador": "Brand Ambassador",
    "youtube_thumbnail": "YouTube Thumbnail",
}

STYLE_PROMPTS = {
    "instagram_ad": "vibrant lifestyle advertising background, creator economy, warm cinematic gradient, polished social media campaign, premium studio depth",
    "linkedin_post": "professional corporate advertising background, clean trust-building business campaign, navy blue lighting, modern technology brand feel",
    "product_poster": "dramatic product launch advertising background, cinematic spotlight, luxury retail campaign, high contrast, premium stage lighting",
    "brand_ambassador": "luxury brand ambassador advertising background, editorial magazine campaign, soft warm lighting, aspirational premium lifestyle",
    "youtube_thumbnail": "high-impact creator thumbnail background, bold energetic lighting, strong contrast, click-worthy advertising composition",
}

THEMES = {
    "instagram_ad": {
        "bg": ((31, 16, 78), (189, 45, 122), (255, 154, 80)),
        "accent": (255, 221, 76),
        "accent2": (255, 79, 121),
        "dark": (15, 13, 28),
        "ink": (255, 255, 255),
        "muted": (246, 220, 255),
    },
    "linkedin_post": {
        "bg": ((5, 18, 39), (12, 78, 139), (214, 239, 255)),
        "accent": (82, 197, 255),
        "accent2": (161, 225, 255),
        "dark": (6, 18, 35),
        "ink": (255, 255, 255),
        "muted": (210, 232, 255),
    },
    "product_poster": {
        "bg": ((5, 6, 18), (31, 22, 54), (239, 150, 51)),
        "accent": (255, 205, 72),
        "accent2": (255, 87, 52),
        "dark": (9, 9, 18),
        "ink": (255, 255, 255),
        "muted": (255, 229, 200),
    },
    "brand_ambassador": {
        "bg": ((42, 24, 22), (147, 81, 55), (250, 219, 168)),
        "accent": (255, 225, 162),
        "accent2": (225, 145, 87),
        "dark": (29, 19, 18),
        "ink": (255, 255, 255),
        "muted": (255, 232, 204),
    },
    "youtube_thumbnail": {
        "bg": ((13, 10, 30), (110, 33, 218), (255, 63, 75)),
        "accent": (255, 230, 50),
        "accent2": (255, 70, 86),
        "dark": (10, 8, 24),
        "ink": (255, 255, 255),
        "muted": (241, 218, 255),
    },
}

SUPPORTED_MODES = {"poster", "ai_background", "ai_creative"}


# -----------------------------------------------------------------------------
# Fonts, image geometry and utility helpers
# -----------------------------------------------------------------------------
def _safe_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    size = max(8, int(size))
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fit_cover(img: Image.Image, size: Tuple[int, int], centering: Tuple[float, float] = (0.5, 0.5)) -> Image.Image:
    img = ImageOps.exif_transpose(img).convert("RGB")
    return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS, centering=centering)


def _fit_contain(img: Image.Image, size: Tuple[int, int]) -> Image.Image:
    img = ImageOps.exif_transpose(img).convert("RGBA")
    img.thumbnail(size, Image.Resampling.LANCZOS)
    return img


def _rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def _draw_round_rect(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], radius: int, fill, outline=None, width: int = 1):
    try:
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    except TypeError:
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline)


def _drop_shadow(size: Tuple[int, int], radius: int = 30, opacity: int = 120) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, opacity))
    return layer.filter(ImageFilter.GaussianBlur(radius))


def _paste_with_shadow(canvas: Image.Image, img: Image.Image, pos: Tuple[int, int], radius: int = 30, opacity: int = 120, offset: Tuple[int, int] | None = None):
    x, y = pos
    ox, oy = offset or (max(6, radius // 3), max(10, radius // 2))
    canvas.alpha_composite(_drop_shadow(img.size, radius=radius, opacity=opacity), (x + ox, y + oy))
    canvas.alpha_composite(img, (x, y))


def _alpha_has_cutout(img: Image.Image) -> bool:
    if img.mode != "RGBA":
        return False
    try:
        lo, hi = img.getchannel("A").getextrema()
        return lo < 235 and hi > 20
    except Exception:
        return False


def _trim_alpha(img: Image.Image, pad: int = 18) -> Image.Image:
    img = img.convert("RGBA")
    bbox = img.getchannel("A").getbbox()
    if not bbox:
        return img
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(img.width, x2 + pad)
    y2 = min(img.height, y2 + pad)
    return img.crop((x1, y1, x2, y2))


def _refine_alpha_edges(img: Image.Image, blur_radius: float = 1.2) -> Image.Image:
    """Feather alpha edge transition zone only — keeps hard interior/exterior intact."""
    if img.mode != "RGBA":
        return img.convert("RGBA")
    r, g, b, a = img.split()
    a_arr = np.array(a, dtype=np.float32)
    a_blurred = np.array(a.filter(ImageFilter.GaussianBlur(blur_radius)), dtype=np.float32)
    edge_mask = (a_arr > 8) & (a_arr < 248)
    result = a_arr.copy()
    result[edge_mask] = a_blurred[edge_mask]
    return Image.merge("RGBA", (r, g, b, Image.fromarray(result.astype(np.uint8))))


def _extract_dominant_color(img: Image.Image) -> Tuple[int, int, int]:
    """Return dominant mid-tone color from an image (excludes near-black/near-white)."""
    small = img.convert("RGB").resize((60, 60), Image.Resampling.LANCZOS)
    arr = np.array(small, dtype=np.float32).reshape(-1, 3)
    brightness = arr.mean(axis=1)
    mid = arr[(brightness > 30) & (brightness < 220)]
    if len(mid) == 0:
        mid = arr
    return tuple(int(c) for c in mid.mean(axis=0).clip(0, 255))


def _apply_ambient_tint(cutout: Image.Image, bg: Image.Image, strength: float = 0.14) -> Image.Image:
    """
    Tint a cutout with the background's ambient light color so the subject looks
    naturally lit by the scene rather than pasted on.
    Samples the top-centre 20% of the background as the key-light region.
    """
    if cutout.mode != "RGBA":
        cutout = cutout.convert("RGBA")
    bw, bh = bg.size
    sample = bg.convert("RGB").crop((bw // 4, 0, 3 * bw // 4, max(1, bh // 5)))
    avg = np.array(sample, dtype=np.float32).reshape(-1, 3).mean(axis=0).clip(0, 255)
    tint_color = tuple(int(c) for c in avg)
    r, g, b, a = cutout.split()
    rgb = Image.merge("RGB", (r, g, b))
    tint = Image.new("RGB", cutout.size, tint_color)
    tinted = Image.blend(rgb, tint, strength)
    return Image.merge("RGBA", (*tinted.split(), a))


def _finalize_output(img: Image.Image) -> Image.Image:
    """Apply final output polish: mild sharpening + vibrance + micro contrast boost."""
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
    img = ImageEnhance.Color(img).enhance(1.12)
    img = ImageEnhance.Contrast(img).enhance(1.06)
    return img


# birefnet-general is a transformer model that consumes 800MB+ runtime RAM even
# on small inputs (internal 1024×1024 tensors). Use U-Net models instead —
# they give good cutout quality at a fraction of the memory cost.
_REMBG_MODEL_PREFERENCE = ["isnet-general-use", "u2net"]


def _rembg_model_cached(model_name: str) -> bool:
    """Return True only if the rembg model ONNX is already on disk (no download triggered)."""
    cache_path = Path.home() / ".u2net" / f"{model_name}.onnx"
    return cache_path.exists()


@lru_cache(maxsize=1)
def _rembg_session():
    """Return a cached rembg session using only pre-downloaded models.
    Never triggers a model download — a download during a user request would hang
    for minutes. Run `python -c "from rembg import new_session; new_session('u2net')"` once
    to pre-download the model, then restart the server."""
    try:
        from rembg import new_session  # type: ignore

        for model in _REMBG_MODEL_PREFERENCE:
            if not _rembg_model_cached(model):
                continue  # skip ALL models not yet on disk — no on-demand downloads
            try:
                session = new_session(model)
                print(f"[BG REMOVE] session created: {model}")
                return session
            except Exception:
                continue
        print("[BG REMOVE] no rembg model found on disk — skipping background removal")
        return None
    except Exception as exc:
        print("[BG REMOVE] rembg unavailable:", type(exc).__name__, str(exc)[:220])
        return None


def _try_remove_background(img: Image.Image, kind: str = "image") -> Image.Image:
    """Use rembg when available; skip if the image already has a proper alpha cutout."""
    original = ImageOps.exif_transpose(img).convert("RGBA")

    # Skip re-removal if the image already has a meaningful transparent cutout
    # (e.g., already processed in compose_ad Step 1).
    if _alpha_has_cutout(original):
        return original

    try:
        from rembg import remove  # type: ignore

        session = _rembg_session()
        if session is None:
            return original

        # Try two sizes: 640px first (safe for birefnet on CPU), 512px on OOM.
        for max_side in (640, 512):
            try:
                working = original.copy()
                if max(working.size) > max_side:
                    ratio = max_side / max(working.size)
                    working = working.resize(
                        (int(working.width * ratio), int(working.height * ratio)),
                        Image.Resampling.LANCZOS,
                    )
                output = remove(working, session=session)
                if isinstance(output, Image.Image):
                    return _trim_alpha(output.convert("RGBA"), pad=20)
                break
            except Exception as exc:
                msg = str(exc).lower()
                if "allocation" in msg or "memory" in msg or "oom" in msg:
                    print(f"[BG REMOVE] {kind} OOM at {max_side}px — retrying smaller")
                    continue
                print(f"[BG REMOVE] {kind} fallback:", type(exc).__name__, str(exc)[:220])
                break
    except Exception as exc:
        print(f"[BG REMOVE] {kind} fallback:", type(exc).__name__, str(exc)[:220])
    return original


# -----------------------------------------------------------------------------
# Premium visual engine
# -----------------------------------------------------------------------------
def _premium_background(width: int, height: int, style: str, accent_color: tuple | None = None) -> Image.Image:
    theme = THEMES.get(style, THEMES["instagram_ad"])
    c1, c2, c3 = theme["bg"]

    # Blend product dominant color 20% into mid-gradient stop for custom palette.
    if accent_color:
        blend = 0.20
        c2 = tuple(int(c2[i] * (1 - blend) + accent_color[i] * blend) for i in range(3))

    # Build a small gradient then upscale for speed.
    small_w = 360
    small_h = max(220, int(small_w * height / width))
    base = Image.new("RGB", (small_w, small_h), c1)
    px = base.load()
    for y in range(small_h):
        yy = y / max(1, small_h - 1)
        for x in range(small_w):
            xx = x / max(1, small_w - 1)
            dist = math.sqrt((xx - 0.86) ** 2 + (yy - 0.28) ** 2)
            t = min(1.0, max(0.0, xx * 0.64 + yy * 0.48 - dist * 0.20))
            if t < 0.52:
                k = t / 0.52
                col = tuple(int(c1[i] * (1 - k) + c2[i] * k) for i in range(3))
            else:
                k = (t - 0.52) / 0.48
                col = tuple(int(c2[i] * (1 - k) + c3[i] * k) for i in range(3))
            px[x, y] = col
    canvas = base.resize((width, height), Image.Resampling.BICUBIC).convert("RGBA")

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    accent = theme["accent"]
    accent2 = theme["accent2"]

    # Studio spotlights and depth glows.
    glows = [
        (0.75, 0.26, 0.54, 0.40, accent, 70),
        (0.20, 0.76, 0.54, 0.42, accent2, 42),
        (0.88, 0.84, 0.42, 0.26, (255, 255, 255), 28),
    ]
    for cxp, cyp, wp, hp, color, alpha in glows:
        gw, gh = int(width * wp), int(height * hp)
        glow = Image.new("RGBA", (gw, gh), (*color, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((0, 0, gw, gh), fill=(*color, alpha))
        glow = glow.filter(ImageFilter.GaussianBlur(max(28, width // 24)))
        overlay.alpha_composite(glow, (int(width * cxp - gw / 2), int(height * cyp - gh / 2)))

    # Diagonal premium light ribbons.
    ribbon = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ribbon)
    for i, alpha in enumerate([34, 22, 16]):
        y = int(height * (0.62 + i * 0.08))
        rd.polygon(
            [(-80, y), (width + 80, int(y - height * 0.17)), (width + 80, int(y - height * 0.11)), (-80, int(y + height * 0.06))],
            fill=(255, 255, 255, alpha),
        )
    ribbon = ribbon.filter(ImageFilter.GaussianBlur(8))
    overlay = Image.alpha_composite(overlay, ribbon)

    # Style specific energy accents.
    random.seed(f"pixolab-v4-{style}-{width}-{height}")
    if style in {"instagram_ad", "youtube_thumbnail", "product_poster"}:
        for _ in range(34 if style != "youtube_thumbnail" else 46):
            x = random.randint(0, width)
            y = random.randint(0, height)
            r = random.randint(max(3, width // 400), max(9, width // 120))
            col = accent if random.random() > 0.45 else accent2
            d.ellipse((x - r, y - r, x + r, y + r), fill=(*col, random.randint(16, 45)))
    if style == "linkedin_post":
        step = max(46, width // 18)
        for x in range(0, width + step, step):
            d.line((x, 0, x - int(width * 0.18), height), fill=(255, 255, 255, 14), width=1)
        for y in range(0, height + step, step):
            d.line((0, y, width, y - int(height * 0.12)), fill=(255, 255, 255, 12), width=1)

    # Bottom shelf / ground plane.
    y_base = int(height * 0.76)
    d.polygon([(0, y_base), (width, int(y_base - height * 0.06)), (width, height), (0, height)], fill=(0, 0, 0, 58))
    return Image.alpha_composite(canvas, overlay)


def _add_noise_texture(canvas: Image.Image, opacity: int = 4) -> Image.Image:
    width, height = canvas.size
    noise = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    px = noise.load()
    for _ in range(max(3200, width * height // 240)):
        x = random.randrange(width)
        y = random.randrange(height)
        v = random.randrange(218, 255)
        px[x, y] = (v, v, v, opacity)
    return Image.alpha_composite(canvas, noise.filter(ImageFilter.GaussianBlur(0.25)))


def _text_wh(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, stroke_width: int = 0) -> Tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    return box[2] - box[0], box[3] - box[1]


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int = 3) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if _text_wh(draw, candidate, font)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len(" ".join(lines).split()) < len(words):
        while lines[-1] and _text_wh(draw, lines[-1] + "…", font)[0] > max_width:
            lines[-1] = lines[-1][:-1].rstrip()
        lines[-1] = lines[-1] + "…"
    return lines[:max_lines]


def _font_for_block(draw: ImageDraw.ImageDraw, text: str, start: int, minimum: int, max_width: int, max_lines: int, bold: bool = True) -> ImageFont.ImageFont:
    for size in range(int(start), int(minimum) - 1, -2):
        font = _safe_font(size, bold=bold)
        lines = _wrap_lines(draw, text, font, max_width=max_width, max_lines=max_lines)
        if lines and all(_text_wh(draw, line, font)[0] <= max_width for line in lines):
            return font
    return _safe_font(minimum, bold=bold)


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    pos: Tuple[int, int],
    font: ImageFont.ImageFont,
    fill,
    max_width: int,
    max_lines: int = 3,
    line_spacing: int = 6,
    stroke_fill=None,
    stroke_width: int = 0,
) -> int:
    x, y = pos
    for line in _wrap_lines(draw, text, font, max_width, max_lines=max_lines):
        draw.text((x, y), line, font=font, fill=fill, stroke_fill=stroke_fill, stroke_width=stroke_width)
        y += _text_wh(draw, line, font, stroke_width=stroke_width)[1] + line_spacing
    return y


def _draw_pill(canvas: Image.Image, xy: Tuple[int, int], label: str, accent: Tuple[int, int, int], dark: Tuple[int, int, int]) -> int:
    draw = ImageDraw.Draw(canvas)
    label = (label or "Ad Creative").strip()[:34]
    font = _safe_font(max(16, canvas.width // 58), bold=True)
    tw, th = _text_wh(draw, label.upper(), font)
    pad_x, pad_y = 20, 9
    x, y = xy
    box = (x, y, x + tw + pad_x * 2, y + th + pad_y * 2)
    _draw_round_rect(draw, box, radius=999, fill=(*accent, 235), outline=(255, 255, 255, 130), width=1)
    draw.text((x + pad_x, y + pad_y - 1), label.upper(), font=font, fill=(*dark, 255))
    return box[3]


def _draw_cta(canvas: Image.Image, xy: Tuple[int, int], cta: str, accent: Tuple[int, int, int], dark: Tuple[int, int, int], max_width: int) -> Tuple[int, int]:
    draw = ImageDraw.Draw(canvas)
    text = (cta or "Order Now").strip()[:28]
    font = _safe_font(max(18, canvas.width // 54), bold=True)
    tw, th = _text_wh(draw, text, font)
    w = min(max_width, tw + 58)
    h = th + 28
    x, y = xy
    _draw_round_rect(draw, (x + 6, y + 8, x + w + 6, y + h + 8), radius=h // 2, fill=(0, 0, 0, 78))
    _draw_round_rect(draw, (x, y, x + w, y + h), radius=h // 2, fill=(*accent, 248), outline=(255, 255, 255, 170), width=2)
    draw.text((x + (w - tw) // 2, y + (h - th) // 2 - 2), text, font=font, fill=(*dark, 255))
    return w, h


def _layout_for(style: str, width: int, height: int) -> dict:
    # Samsung-style: person full-height on one side, product + text on the other.
    m = int(min(width, height) * 0.04)
    if style == "youtube_thumbnail":
        # Person on right (full height), text + product on left.
        person_x = int(width * 0.44)
        return {
            "text": (m, m, int(width * 0.40), int(height * 0.68)),
            "person": (person_x, 0, width - person_x, height),
            "product": (int(width * 0.22), int(height * 0.22), int(width * 0.28), int(height * 0.60)),
            "halo": (int(width * 0.20), int(height * 0.10), int(width * 0.40), int(height * 0.78)),
        }
    if style == "linkedin_post":
        # Person on right (full height), text + product on left.
        person_x = int(width * 0.46)
        return {
            "text": (m, m, int(width * 0.40), int(height * 0.80)),
            "person": (person_x, 0, width - person_x, height),
            "product": (int(width * 0.22), int(height * 0.18), int(width * 0.28), int(height * 0.68)),
            "halo": (int(width * 0.20), int(height * 0.08), int(width * 0.38), int(height * 0.82)),
        }
    if height > width:
        # Portrait — person full-height left, text top strip, product lower right.
        person_w = int(width * 0.62)
        right_x = int(width * 0.54)
        right_w = width - right_x - m
        return {
            "text": (m, m, width - m * 2, int(height * 0.20)),
            "person": (0, 0, person_w, height),
            "product": (right_x, int(height * 0.48), right_w, int(height * 0.48)),
            "halo": (int(width * 0.48), int(height * 0.36), int(width * 0.50), int(height * 0.54)),
        }
    # Square (1080×1080) — person full-height left, text + product on right.
    person_w = int(width * 0.62)
    right_x = person_w + m
    right_w = width - right_x - m
    return {
        "text": (right_x, m, right_w, int(height * 0.48)),
        "person": (0, 0, person_w, height),
        "product": (int(width * 0.54), int(height * 0.46), int(width * 0.42), int(height * 0.50)),
        "halo": (int(width * 0.50), int(height * 0.34), int(width * 0.46), int(height * 0.58)),
    }


def _make_person_visual(person_raw: Image.Image, box: Tuple[int, int, int, int], theme: dict) -> Image.Image:
    _, _, w, h = box
    # BG removal was already done in compose_ad Step 1; just check the result.
    person = ImageOps.exif_transpose(person_raw).convert("RGBA")
    is_cutout = _alpha_has_cutout(person)

    if is_cutout:
        person = _refine_alpha_edges(person)
        fitted = _fit_contain(person, (w, h))
        layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        px = (w - fitted.width) // 2
        py = h - fitted.height

        # Rim glow based on alpha silhouette.
        alpha = fitted.getchannel("A")
        glow_alpha = alpha.filter(ImageFilter.GaussianBlur(max(14, w // 22)))
        glow = Image.new("RGBA", fitted.size, (*theme["accent2"], 65))
        glow.putalpha(glow_alpha)
        layer.alpha_composite(glow, (px, py))
        layer.alpha_composite(fitted, (px, py))
        return layer

    # No cutout: show full-bleed portrait with right-edge gradient fade so the
    # person blends naturally into the background (no dark card overlay).
    card = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    portrait = _fit_cover(person_raw, (w, h), centering=(0.5, 0.15)).convert("RGBA")
    fade_w = max(60, int(w * 0.28))
    alpha_arr = np.ones((h, w), dtype=np.float32) * 255
    for i in range(fade_w):
        val = 255.0 * (1.0 - math.cos((i / fade_w) * math.pi / 2))
        alpha_arr[:, w - 1 - i] = val
    old_a = np.array(portrait.getchannel("A"), dtype=np.float32)
    new_a = np.minimum(old_a, alpha_arr).astype(np.uint8)
    r, g, b, _ = portrait.split()
    portrait = Image.merge("RGBA", (r, g, b, Image.fromarray(new_a)))
    card.alpha_composite(portrait)
    return card


def _make_product_visual(product_raw: Image.Image, box: Tuple[int, int, int, int], theme: dict, style: str) -> Image.Image:
    _, _, w, h = box
    layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    # BG removal was already done in compose_ad Step 1; just check the result.
    product = ImageOps.exif_transpose(product_raw).convert("RGBA")
    is_cutout = _alpha_has_cutout(product)
    draw = ImageDraw.Draw(layer)

    if is_cutout:
        product = _refine_alpha_edges(product)
        fitted = _fit_contain(product, (int(w * 0.92), int(h * 0.80)))
        px = (w - fitted.width) // 2
        py = int(h * 0.48 - fitted.height / 2)
        py = max(2, min(py, h - fitted.height - 26))

        # Subtle ambient glow behind product only when there is a real cutout.
        glow = Image.new("RGBA", (w, h), (*theme["accent"], 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((int(w * 0.04), int(h * 0.12), int(w * 0.96), int(h * 0.88)), fill=(*theme["accent"], 36))
        glow = glow.filter(ImageFilter.GaussianBlur(max(18, w // 16)))
        layer = Image.alpha_composite(layer, glow)

        # Contact shadow beneath product.
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        base_y = min(h - 34, py + fitted.height - 12)
        sd.ellipse((int(w * 0.22), base_y, int(w * 0.78), base_y + max(22, h // 13)), fill=(0, 0, 0, 72))
        shadow = shadow.filter(ImageFilter.GaussianBlur(8))
        layer = Image.alpha_composite(layer, shadow)
        layer.alpha_composite(fitted, (px, py))
    else:
        # No cutout — clean white product card with subtle drop shadow.
        card_w, card_h = int(w * 0.88), int(h * 0.80)
        card_x, card_y = (w - card_w) // 2, int(h * 0.06)
        radius = max(24, min(card_w, card_h) // 9)
        shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((card_x + 5, card_y + 8, card_x + card_w + 5, card_y + card_h + 8), radius=radius, fill=(0, 0, 0, 70))
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        layer = Image.alpha_composite(layer, shadow)
        draw = ImageDraw.Draw(layer)
        _draw_round_rect(draw, (card_x, card_y, card_x + card_w, card_y + card_h), radius, fill=(252, 252, 252, 245))
        inner = _fit_cover(product_raw, (card_w - 28, card_h - 28), centering=(0.5, 0.5)).convert("RGBA")
        inner.putalpha(_rounded_mask(inner.size, max(18, radius - 12)))
        layer.alpha_composite(inner, (card_x + 14, card_y + 14))

    draw = ImageDraw.Draw(layer)
    chip_text = "PRODUCT SPOTLIGHT" if style != "youtube_thumbnail" else "NEW DROP"
    chip_font = _safe_font(max(13, w // 23), bold=True)
    tw, th = _text_wh(draw, chip_text, chip_font)
    chip_w, chip_h = tw + 28, th + 16
    chip_x, chip_y = max(8, w - chip_w - 8), h - chip_h - 4
    _draw_round_rect(draw, (chip_x, chip_y, chip_x + chip_w, chip_y + chip_h), chip_h // 2, fill=(*theme["dark"], 190), outline=(*theme["accent"], 135), width=1)
    draw.text((chip_x + 14, chip_y + 7), chip_text, font=chip_font, fill=(255, 255, 255, 235))
    return layer


def _draw_motion_accents(canvas: Image.Image, layout: dict, style: str, theme: dict):
    width, height = canvas.size
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    accent, accent2 = theme["accent"], theme["accent2"]
    hx, hy, hw, hh = layout["halo"]

    # Main product halo.
    d.ellipse((hx, hy, hx + hw, hy + hh), fill=(*accent, 38))
    d.ellipse((hx + int(hw * 0.22), hy + int(hh * 0.18), hx + hw, hy + hh), fill=(*accent2, 22))

    # Orbit lines around product area.
    for i in range(4):
        pad = int(min(hw, hh) * (0.03 + i * 0.09))
        alpha = 70 - i * 12
        d.arc((hx + pad, hy + pad, hx + hw - pad, hy + hh - pad), start=205 + i * 14, end=345 + i * 12, fill=(255, 255, 255, alpha), width=max(2, width // 360))

    # Style energy marks.
    if style == "youtube_thumbnail":
        for i in range(10):
            x = int(width * (0.50 + i * 0.045))
            y = int(height * (0.12 + (i % 3) * 0.08))
            r = max(8, width // 95)
            d.line((x - r, y, x + r, y), fill=(*accent, 170), width=max(3, width // 210))
            d.line((x, y - r, x, y + r), fill=(*accent, 170), width=max(3, width // 210))
    else:
        for i in range(8):
            x = int(width * (0.05 + i * 0.12))
            y = int(height * (0.84 + (i % 2) * 0.05))
            d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(*accent, 76))

    overlay = overlay.filter(ImageFilter.GaussianBlur(0.4))
    canvas.alpha_composite(overlay)


def _draw_text_panel(
    canvas: Image.Image,
    box: Tuple[int, int, int, int],
    style: str,
    brand_name: str,
    headline: str,
    subheadline: str,
    cta: str,
    plan: str,
    include_watermark: bool = True,
):
    width, height = canvas.size
    x, y, w, h = box
    theme = THEMES.get(style, THEMES["instagram_ad"])
    accent, dark = theme["accent"], theme["dark"]

    # Compact but premium glass card. Text never overlaps the subject/product.
    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    radius = max(28, min(w, h) // 8)
    _draw_round_rect(pd, (0, 0, w, h), radius, fill=(*dark, 178), outline=(255, 255, 255, 46), width=2)
    pd.rounded_rectangle((2, 2, w - 2, max(28, int(h * 0.34))), radius=radius, fill=(255, 255, 255, 14))
    # Accent edge
    pd.rounded_rectangle((0, 0, max(9, width // 120), h), radius=max(6, width // 260), fill=(*accent, 235))
    canvas.alpha_composite(_drop_shadow((w, h), radius=26, opacity=100), (x + 7, y + 10))
    canvas.alpha_composite(panel, (x, y))

    draw = ImageDraw.Draw(canvas)
    pad = max(22, int(min(width, height) * 0.027))
    cx = x + pad + max(7, width // 150)
    cy = y + pad

    label = brand_name.strip() or STYLE_LABELS.get(style, "Ad Creative")
    cy = _draw_pill(canvas, (cx, cy), label, accent, dark) + max(12, height // 105)

    h_text = (headline or "Launch Your Product").strip()
    max_lines = 2 if style in {"youtube_thumbnail", "linkedin_post"} else 3
    start_size = int(width * (0.058 if style != "youtube_thumbnail" else 0.066))
    min_size = int(width * (0.031 if style != "linkedin_post" else 0.026))
    font = _font_for_block(draw, h_text, start_size, min_size, w - pad * 2, max_lines=max_lines, bold=True)
    stroke = max(1, width // 480) if style == "youtube_thumbnail" else 0
    cy = _draw_wrapped_text(
        draw,
        h_text,
        (cx, cy),
        font,
        fill=(255, 255, 255, 255),
        max_width=w - pad * 2,
        max_lines=max_lines,
        line_spacing=max(5, height // 150),
        stroke_fill=(0, 0, 0, 170),
        stroke_width=stroke,
    )

    if subheadline:
        cy += max(7, height // 135)
        sub_font = _safe_font(max(16, int(width * 0.020)), bold=False)
        cy = _draw_wrapped_text(
            draw,
            subheadline.strip(),
            (cx, cy),
            sub_font,
            fill=(*theme["muted"], 230),
            max_width=w - pad * 2,
            max_lines=2,
            line_spacing=max(5, height // 170),
            stroke_fill=(0, 0, 0, 95),
            stroke_width=1,
        )

    if cta:
        cy += max(14, height // 72)
        _draw_cta(canvas, (cx, min(cy, y + h - 74)), cta, accent, dark, max_width=min(w - pad * 2, int(width * 0.34)))

    if settings.watermark_free_plan and include_watermark and plan == "free":
        wm_font = _safe_font(max(14, width // 70), bold=True)
        wm = "pixolab.online"
        tw, th = _text_wh(draw, wm, wm_font)
        ww, wh = tw + 30, th + 18
        wx, wy = width - ww - 22, height - wh - 22
        _draw_round_rect(draw, (wx, wy, wx + ww, wy + wh), radius=18, fill=(0, 0, 0, 148), outline=(255, 255, 255, 32), width=1)
        draw.text((wx + 15, wy + 8), wm, font=wm_font, fill=(255, 255, 255, 230))


def _draw_quality_frame(canvas: Image.Image, style: str, theme: dict):
    width, height = canvas.size
    d = ImageDraw.Draw(canvas)
    # Outer premium frame and subtle corner marks.
    inset = max(10, min(width, height) // 80)
    d.rounded_rectangle((inset, inset, width - inset, height - inset), radius=max(24, inset * 2), outline=(255, 255, 255, 30), width=max(2, width // 520))
    r = max(28, width // 45)
    for sx, sy in [(inset * 2, inset * 2), (width - inset * 2 - r, inset * 2), (inset * 2, height - inset * 2 - r), (width - inset * 2 - r, height - inset * 2 - r)]:
        d.arc((sx, sy, sx + r, sy + r), 180, 270, fill=(*theme["accent"], 95), width=max(2, width // 360))


def build_background_prompt(style: str, brand_name: str = "", headline: str = "", cta: str = "") -> str:
    style_text = STYLE_PROMPTS.get(style, STYLE_PROMPTS["instagram_ad"])
    brand_part = f" for {brand_name} brand" if brand_name else ""
    headline_part = f" Mood inspired by: {headline}." if headline else ""
    return (
        f"Photorealistic commercial advertising studio background only{brand_part}. "
        f"{style_text}. "
        "Cinematic color grading, seamless depth-of-field bokeh, professional studio lighting setup, "
        "ultra-detailed 8K render, premium luxury atmosphere, clean negative space for subject compositing. "
        "STRICT: empty scene — absolutely no people, no hands, no faces, no body parts, "
        "no products, no bottles, no boxes, no phones, no packaging, no logos, "
        "no text, no letters, no numbers, no watermarks."
        f"{headline_part}"
    )


def build_ai_creative_prompt(style: str, brand_name: str = "", headline: str = "") -> str:
    """Prompt for FLUX-style image-to-image models."""
    style_text = STYLE_PROMPTS.get(style, STYLE_PROMPTS["instagram_ad"])
    brand = f" for {brand_name}" if brand_name else ""
    campaign = f" Campaign concept: {headline}." if headline else ""
    return (
        "Transform this reference composition into a premium photorealistic advertising creative. "
        "Preserve the same person's face identity cues, clothing colours, pose direction and overall look. "
        "Preserve the same product shape, colour, packaging and key design cues. "
        "Make the person and product look visually integrated in one commercial campaign with coherent lighting, realistic shadows and depth. "
        "Keep clean negative space for typography; do not render text in the image itself. "
        f"Style: {style_text}{brand}.{campaign} "
        "Avoid random letters, fake logos, distorted face, extra hands, duplicate people, duplicate products, watermark, blurry details."
    )


def build_qwen_edit_prompt(style: str, brand_name: str = "", headline: str = "") -> str:
    """Instruction-style prompt for Qwen-Image-Edit-2509.
    Qwen follows direct editing commands rather than descriptive style phrases.
    """
    style_map = {
        "instagram_ad": "vibrant lifestyle ad with warm cinematic tones",
        "linkedin_post": "clean professional business ad with corporate blue tones",
        "product_poster": "dramatic product-launch poster with cinematic spotlight",
        "brand_ambassador": "luxury editorial brand campaign with soft warm lighting",
        "youtube_thumbnail": "bold high-contrast click-worthy thumbnail",
    }
    look = style_map.get(style, "premium commercial advertisement")
    brand_line = f" for the {brand_name} brand" if brand_name else ""
    headline_line = f" The campaign message is: {headline}." if headline else ""
    return (
        f"Enhance this advertising composite into a polished {look}{brand_line}.{headline_line} "
        "Improve the studio lighting to be dramatic and cinematic. "
        "Make the person look naturally integrated with coherent skin tones and realistic shadows. "
        "Sharpen the product details and add a subtle podium or ground shadow beneath it. "
        "Boost overall sharpness, colour vibrancy and depth-of-field. "
        "Do NOT add any text, letters, watermarks, logos, or new objects. "
        "Do NOT change the layout — keep person on left, product on right."
    )


_qwen_pipe: object | None = None


def _load_qwen_pipeline(token: str) -> object:
    """Lazy-load QwenImageEditPlusPipeline with the Rapid-AIO-V4 distilled transformer.
    Cached globally so the ~14 GB weights are only loaded once per server process.
    Raises RuntimeError if CUDA is unavailable (CPU inference is too slow to be usable).
    """
    global _qwen_pipe
    if _qwen_pipe is not None:
        return _qwen_pipe

    import torch
    from diffusers import QwenImageEditPlusPipeline, QwenImageTransformer2DModel

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available — local Qwen pipeline requires a GPU")

    dtype = torch.bfloat16
    print("[Qwen] Loading Rapid-AIO-V4 transformer (first run downloads weights)...")
    transformer = QwenImageTransformer2DModel.from_pretrained(
        "prithivMLmods/Qwen-Image-Edit-Rapid-AIO-V4",
        torch_dtype=dtype,
        device_map="cuda",
        token=token or None,
    )
    print("[Qwen] Loading QwenImageEditPlusPipeline...")
    pipe = QwenImageEditPlusPipeline.from_pretrained(
        "Qwen/Qwen-Image-Edit-2509",
        transformer=transformer,
        torch_dtype=dtype,
        token=token or None,
    ).to("cuda")
    _qwen_pipe = pipe
    print("[Qwen] Pipeline ready.")
    return _qwen_pipe


def _hf_client_kwargs() -> dict:
    token = (settings.hf_token or "").strip().strip('"').strip("'")
    provider = (getattr(settings, "hf_provider", "") or "").strip().strip('"').strip("'")
    kwargs = {"api_key": token}
    if provider and provider.lower() not in {"auto", "default", "none", "null"}:
        kwargs["provider"] = provider
    return kwargs


def generate_hf_background(prompt: str, width: int, height: int) -> Image.Image | None:
    token = (settings.hf_token or "").strip().strip('"').strip("'")
    if not settings.enable_hf_background:
        print("[HF] Background disabled")
        return None
    if not token:
        print("[HF] Background disabled: HF_TOKEN missing")
        return None
    try:
        from huggingface_hub import InferenceClient

        print("[HF] Generating AI background with", settings.hf_model_id)
        client = InferenceClient(**_hf_client_kwargs())
        image = client.text_to_image(prompt, model=settings.hf_model_id)
        print("[HF] AI background generated")
        return _fit_cover(image, (width, height)).convert("RGBA")
    except Exception as exc:
        print("[HF ERROR] Background generation failed:", type(exc).__name__, str(exc)[:600])
        return None


def generate_hf_creative_scene(base_scene: Image.Image, prompt: str, width: int, height: int) -> Image.Image | None:
    token = (settings.hf_token or "").strip().strip('"').strip("'")
    creative_enabled = bool(getattr(settings, "enable_ai_creative", False))
    model_id = getattr(settings, "hf_creative_model_id", "") or ""
    if not creative_enabled:
        print("[HF] AI Creative disabled")
        return None
    if not token:
        print("[HF] AI Creative disabled: HF_TOKEN missing")
        return None
    if not model_id:
        print("[HF] AI Creative disabled: HF_CREATIVE_MODEL_ID missing")
        return None

    is_qwen = "qwen" in model_id.lower()
    is_flux = "flux" in model_id.lower()

    try:
        import io
        from huggingface_hub import InferenceClient

        buf = io.BytesIO()
        base_scene.convert("RGB").save(buf, format="JPEG", quality=88)
        image_bytes = buf.getvalue()

        print(f"[HF] Refining creative scene with {model_id}...")

        if is_qwen:
            # Qwen-Image-Edit-2509 via wavespeed.
            # The generic WavespeedAIImageToImageTask sends "image" (singular),
            # but wavespeed's Qwen API requires "images" (array). Pass it via
            # **kwargs so it lands in the payload alongside the provider's field.
            import base64
            image_data_url = f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode()}"
            client = InferenceClient(api_key=token, provider="wavespeed")
            image = client.image_to_image(
                image_bytes,
                prompt=prompt,
                model=model_id,
                images=[image_data_url],
            )
        else:
            client = InferenceClient(**_hf_client_kwargs())
            image = client.image_to_image(
                image_bytes,
                prompt=prompt,
                # FLUX models don't support negative prompts; omit to avoid API rejection.
                negative_prompt=None if is_flux else "bad text, misspelled words, random letters, extra fingers, distorted face, duplicate product, duplicate person, low quality, blurry, watermark",
                guidance_scale=3.5 if is_flux else 7.5,
                num_inference_steps=28 if is_flux else 32,
                model=model_id,
            )

        print("[HF] AI Creative scene generated")
        if isinstance(image, Image.Image):
            return _fit_cover(image, (width, height)).convert("RGBA")
        return _fit_cover(Image.open(io.BytesIO(image)), (width, height)).convert("RGBA")
    except StopIteration:
        print(f"[HF ERROR] AI Creative skipped: no inference providers available for {model_id} — model not served on HF inference")
        return None
    except Exception as exc:
        body = getattr(getattr(exc, "response", None), "text", "") or ""
        print("[HF ERROR] AI Creative generation failed:", type(exc).__name__, str(exc)[:800])
        if body:
            print("[HF ERROR] Response body:", body[:600])
        return None


def _render_composite(
    person_raw: Image.Image,
    product_raw: Image.Image,
    bg: Image.Image,
    style: str,
    brand_name: str,
    headline: str,
    subheadline: str,
    cta: str,
    plan: str,
    include_text: bool = True,
    include_watermark: bool = True,
) -> Image.Image:
    width, height = bg.size
    theme = THEMES.get(style, THEMES["instagram_ad"])
    layout = _layout_for(style, width, height)

    canvas = bg.convert("RGBA")
    bg_rgb = bg.convert("RGB")  # kept for ambient tinting — unaffected by canvas overlays

    # A slight depth pass improves text/product contrast without making the poster dull.
    canvas = Image.alpha_composite(canvas, Image.new("RGBA", (width, height), (0, 0, 0, 18 if style != "linkedin_post" else 6)))
    canvas = _add_noise_texture(canvas, opacity=4)
    _draw_motion_accents(canvas, layout, style, theme)

    # Add subject and product with intentional overlap. Product is foreground hero.
    px, py, pw, ph = layout["person"]
    person_visual = _make_person_visual(person_raw, layout["person"], theme)
    person_visual = _apply_ambient_tint(person_visual, bg_rgb)
    _paste_with_shadow(canvas, person_visual, (px, py), radius=max(22, min(width, height) // 34), opacity=125, offset=(10, 14))

    prx, pry, prw, prh = layout["product"]
    product_visual = _make_product_visual(product_raw, layout["product"], theme, style)
    product_visual = _apply_ambient_tint(product_visual, bg_rgb, strength=0.10)
    _paste_with_shadow(canvas, product_visual, (prx, pry), radius=max(26, min(width, height) // 32), opacity=152, offset=(8, 16))

    _draw_quality_frame(canvas, style, theme)

    if include_text:
        _draw_text_panel(canvas, layout["text"], style, brand_name, headline, subheadline, cta, plan, include_watermark=include_watermark)
    return canvas


def compose_ad(
    person_path: Path,
    product_path: Path,
    style: str,
    brand_name: str = "",
    headline: str = "",
    subheadline: str = "",
    cta: str = "",
    mode: str = "poster",
    plan: str = "free",
    person_caption: str = "Brand influencer",
    product_caption: str = "Premium product",
    target_audience: str = "18-35 years old",
) -> tuple[Path, dict]:
    """
    Enhanced compose_ad with integrated pipeline:
    1. Remove backgrounds from images
    2. Generate creative brief with Groq
    3. Generate background using refined prompts
    4. Compose manually with Pillow
    5. Optional: Harmonize with inpainting
    6. Add text manually (no diffusion)
    """
    if mode not in SUPPORTED_MODES:
        mode = "poster"
    width, height = STYLE_DIMENSIONS.get(style, (1080, 1080))

    pipeline_meta = {
        "width": width,
        "height": height,
        "mode": mode,
        "used_hf_background": False,
        "used_ai_creative": False,
        "used_groq": False,
        "used_background_removal": False,
        "used_inpainting": False,
    }

    try:
        # ===== STEP 1: Remove backgrounds (parallel) =====
        print(f"[Pixolab] STEP 1 — background removal  (mode={mode})")
        person_raw = Image.open(person_path)
        product_raw = Image.open(product_path)

        if settings.enable_background_removal:
            # Sequential BG removal in the main thread.
            # Parallel threads caused silent ONNX Runtime failures on Windows;
            # the resolution cap means each image takes ~3-8s — sequential is fast enough.
            print("[Pixolab]   removing background from person image...")
            person_processed = _try_remove_background(person_raw, "person")
            print("[Pixolab]   removing background from product image...")
            product_processed = _try_remove_background(product_raw, "product")
            pipeline_meta["used_background_removal"] = True
            print("[Pixolab]   background removal done")
            # Free the ONNX session from RAM before the Pillow/numpy composition.
            # Without this, the rembg session holds ~150-300 MB and leaves little
            # room for numpy arrays during compositing.
            import gc as _gc
            _rembg_session.cache_clear()
            _gc.collect()
            print("[Pixolab]   rembg session freed")
        else:
            person_processed = person_raw.convert("RGBA")
            product_processed = product_raw.convert("RGBA")

        # ===== STEP 2: Generate creative brief with Groq =====
        print("[Pixolab] STEP 2 — Groq creative brief")
        groq_concept = None
        # Skip Groq for poster mode — saves 5-10s with no meaningful benefit
        if mode != "poster" and settings.enable_groq_creative and settings.groq_api_key:
            try:
                groq_client = groq_module.initialize_groq_client(settings.groq_api_key)
                if groq_client:
                    print("[Pixolab]   calling Groq API (timeout=8s)...")
                    groq_concept = groq_module.generate_ad_concept(
                        groq_client=groq_client,
                        product_caption=product_caption,
                        person_caption=person_caption,
                        brand_name=brand_name,
                        style=style,
                        target_audience=target_audience,
                        user_headline=headline,
                        user_subheadline=subheadline,
                        user_cta=cta,
                    )
                    pipeline_meta["used_groq"] = True
                    print("[Pixolab]   Groq brief done")
            except Exception as e:
                print(f"[Pixolab]   Groq failed: {e} — using fallback")
                groq_concept = None
        
        # Select prompt builder based on which creative model is configured.
        _creative_model = (getattr(settings, "hf_creative_model_id", "") or "").lower()
        _using_qwen = "qwen" in _creative_model

        if groq_concept:
            background_prompt = groq_concept.get("background_prompt", "")
            creative_prompt = groq_concept.get("background_prompt", "")
            final_headline = headline or groq_concept.get("headline", "")
            final_subheadline = subheadline or groq_concept.get("subheadline", "")
            final_cta = cta or groq_concept.get("cta", "")
        else:
            background_prompt = build_background_prompt(style, brand_name, headline, cta)
            creative_prompt = (
                build_qwen_edit_prompt(style, brand_name, headline)
                if _using_qwen
                else build_ai_creative_prompt(style, brand_name, headline)
            )
            final_headline = headline
            final_subheadline = subheadline
            final_cta = cta

        # ===== STEP 3: Generate background =====
        print("[Pixolab] STEP 3 — background generation")
        product_accent = _extract_dominant_color(product_raw)

        bg = None
        if mode in {"ai_background", "ai_creative"}:
            print(f"[Pixolab]   calling HF background ({settings.hf_model_id})...")
            bg = generate_hf_background(background_prompt, width, height)
            if bg:
                pipeline_meta["used_hf_background"] = True
                print("[Pixolab]   HF background done")
            else:
                print("[Pixolab]   HF background failed, using procedural fallback")

        if bg is None:
            print("[Pixolab]   generating procedural background...")
            bg = _premium_background(width, height, style, accent_color=product_accent)
            print("[Pixolab]   procedural background done")

        # ===== STEP 4: Compose with Pillow (precise control) =====
        print("[Pixolab] STEP 4 — Pillow composition")
        final_canvas = _render_composite(
            person_raw=person_processed,
            product_raw=product_processed,
            bg=bg,
            style=style,
            brand_name=brand_name,
            headline=final_headline,
            subheadline=final_subheadline,
            cta=final_cta,
            plan=plan,
            include_text=True,
            include_watermark=True,
        )

        # ===== STEP 5: Optional inpainting harmonization =====
        if mode == "ai_creative":
            logger.info("Step 5: AI Creative - refining with inpainting")
            if inpainting.should_use_inpainting(settings.enable_inpainting, plan):
                guide_scene = _render_composite(
                    person_raw=person_processed,
                    product_raw=product_processed,
                    bg=bg,
                    style=style,
                    brand_name=brand_name,
                    headline=final_headline,
                    subheadline=final_subheadline,
                    cta=final_cta,
                    plan=plan,
                    include_text=False,
                    include_watermark=False,
                )
                harmonized = inpainting.harmonize_poster_with_inpainting(
                    composite_image=guide_scene,
                    prompt=creative_prompt,
                    model_id=settings.inpainting_model_id,
                    hf_token=settings.hf_token,
                    width=width,
                    height=height,
                )
                if harmonized:
                    final_canvas = harmonized
                    pipeline_meta["used_inpainting"] = True
                    # Re-add text after inpainting
                    _draw_text_panel(
                        final_canvas,
                        _layout_for(style, width, height)["text"],
                        style,
                        brand_name,
                        final_headline,
                        final_subheadline,
                        final_cta,
                        plan,
                        include_watermark=True,
                    )
            else:
                # Standard AI creative without inpainting
                guide_scene = _render_composite(
                    person_raw=person_processed,
                    product_raw=product_processed,
                    bg=bg,
                    style=style,
                    brand_name=brand_name,
                    headline=final_headline,
                    subheadline=final_subheadline,
                    cta=final_cta,
                    plan=plan,
                    include_text=False,
                    include_watermark=False,
                )
                ai_scene = generate_hf_creative_scene(guide_scene, creative_prompt, width, height)
                if ai_scene is not None:
                    pipeline_meta["used_ai_creative"] = True
                    final_canvas = ai_scene
                    _draw_text_panel(
                        final_canvas,
                        _layout_for(style, width, height)["text"],
                        style,
                        brand_name,
                        final_headline,
                        final_subheadline,
                        final_cta,
                        plan,
                        include_watermark=True,
                    )

        # ===== STEP 6: Save final output =====
        print("[Pixolab] STEP 6 — finalizing and saving")
        out_name = f"pixolab_{uuid.uuid4().hex}.png"
        out_path = settings.storage_dir / "results" / out_name
        final_rgb = _finalize_output(final_canvas.convert("RGB"))
        final_rgb.save(out_path, quality=96, optimize=True)

        pipeline_meta["prompt"] = creative_prompt if mode == "ai_creative" else background_prompt
        print(f"[Pixolab] DONE — {out_path.name}")
        return out_path, pipeline_meta

    except Exception as e:
        print(f"[Pixolab] ERROR in compose_ad: {type(e).__name__}: {e}")
        logger.error(f"Poster generation failed: {e}")
        raise


# =============================================================================
# Template-based rendering engine — professional per-layout poster generator
# =============================================================================

def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (10, 10, 30)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ── Gradient canvas builder ───────────────────────────────────────────────────

def _tmpl_gradient_canvas(width: int, height: int, colors: list, direction: str = "vertical") -> Image.Image:
    """Multi-stop gradient canvas. direction: vertical | diagonal | radial."""
    sw, sh = 480, max(300, int(480 * height / width))
    base = Image.new("RGB", (sw, sh))
    px = base.load()
    n = max(1, len(colors) - 1)
    for y in range(sh):
        for x in range(sw):
            if direction == "diagonal":
                t = (x / sw * 0.55 + (1.0 - y / sh) * 0.45)
            elif direction == "radial":
                dx, dy = (x / sw - 0.5) * 2, (y / sh - 0.5) * 2
                t = 1.0 - min(1.0, math.sqrt(dx*dx + dy*dy))
            else:
                t = y / max(1, sh - 1)
            t = max(0.0, min(1.0, t))
            seg = min(int(t * n), n - 1)
            lt = t * n - seg
            c1, c2 = colors[seg], colors[min(seg + 1, n)]
            px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * lt) for i in range(3))
    return base.resize((width, height), Image.Resampling.BICUBIC).convert("RGBA")


def _tmpl_add_glow(canvas: Image.Image, cx: int, cy: int, rx: int, ry: int, rgb: tuple, alpha: int) -> None:
    """Soft elliptical glow at (cx, cy)."""
    gw, gh = max(4, rx * 2), max(4, ry * 2)
    gimg = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
    ImageDraw.Draw(gimg).ellipse((0, 0, gw, gh), fill=(*rgb, alpha))
    gimg = gimg.filter(ImageFilter.GaussianBlur(max(gw, gh) // 4))
    canvas.alpha_composite(gimg, (max(0, cx - rx), max(0, cy - ry)))


# ── Template background generators ───────────────────────────────────────────

def _tmpl_bg_tech(width: int, height: int, preview_colors: list) -> Image.Image:
    """Deep navy with blue/cyan energy glows — tech aesthetic."""
    c1 = _hex_to_rgb(preview_colors[0]) if len(preview_colors) > 0 else (4, 5, 20)
    c2 = _hex_to_rgb(preview_colors[1]) if len(preview_colors) > 1 else (8, 18, 55)
    c3 = _hex_to_rgb(preview_colors[2]) if len(preview_colors) > 2 else (5, 25, 70)
    canvas = _tmpl_gradient_canvas(width, height, [c1, c2, c3])
    _tmpl_add_glow(canvas, int(width * 0.68), int(height * 0.45), int(width * 0.38), int(height * 0.30), (0, 80, 220), 55)
    _tmpl_add_glow(canvas, int(width * 0.70), int(height * 0.38), int(width * 0.20), int(height * 0.16), (0, 150, 255), 75)
    _tmpl_add_glow(canvas, int(width * 0.28), int(height * 0.60), int(width * 0.28), int(height * 0.24), (0, 50, 160), 35)
    od = ImageDraw.Draw(canvas)
    for y in range(0, height, max(28, height // 30)):
        od.line([(0, y), (width, y)], fill=(255, 255, 255, 5), width=1)
    for x in range(0, width, max(55, width // 14)):
        od.line([(x, 0), (x, height)], fill=(0, 120, 255, 4), width=1)
    return canvas


def _tmpl_bg_elegance(width: int, height: int, preview_colors: list) -> Image.Image:
    """Near-black with warm amber glow — luxury editorial."""
    c1 = _hex_to_rgb(preview_colors[0]) if len(preview_colors) > 0 else (10, 10, 12)
    c2 = _hex_to_rgb(preview_colors[1]) if len(preview_colors) > 1 else (18, 18, 22)
    canvas = _tmpl_gradient_canvas(width, height, [c1, c2])
    _tmpl_add_glow(canvas, int(width * 0.74), int(height * 0.74), int(width * 0.40), int(height * 0.32), (180, 120, 40), 48)
    _tmpl_add_glow(canvas, int(width * 0.25), int(height * 0.44), int(width * 0.32), int(height * 0.36), (40, 60, 160), 30)
    od = ImageDraw.Draw(canvas)
    for i in range(0, width + height, max(38, width // 16)):
        od.line([(i, 0), (0, i)], fill=(255, 255, 255, 4), width=1)
    return canvas


def _tmpl_bg_performance(width: int, height: int, preview_colors: list) -> Image.Image:
    """Deep purple with central radial explosion — action/drama."""
    c1 = _hex_to_rgb(preview_colors[0]) if len(preview_colors) > 0 else (6, 0, 14)
    c2 = _hex_to_rgb(preview_colors[1]) if len(preview_colors) > 1 else (22, 8, 58)
    c3 = _hex_to_rgb(preview_colors[2]) if len(preview_colors) > 2 else (38, 8, 88)
    sw, sh = 480, max(300, int(480 * height / width))
    base = Image.new("RGB", (sw, sh))
    px = base.load()
    cx_c, cy_c = sw * 0.5, sh * 0.52
    for y in range(sh):
        for x in range(sw):
            dist = math.sqrt((x - cx_c)**2 + (y - cy_c)**2)
            t = 1.0 - min(1.0, dist / (math.sqrt(cx_c**2 + cy_c**2)) * 1.15)
            seg = min(int(t * 2), 1)
            lt = t * 2 - seg
            cs = [c1, c2, c3]
            col = tuple(int(cs[seg][i] + (cs[min(seg+1, 2)][i] - cs[seg][i]) * lt) for i in range(3))
            px[x, y] = col
    canvas = base.resize((width, height), Image.Resampling.BICUBIC).convert("RGBA")
    _tmpl_add_glow(canvas, width//2, int(height * 0.50), int(width * 0.44), int(height * 0.34), (30, 80, 255), 68)
    _tmpl_add_glow(canvas, width//2, int(height * 0.44), int(width * 0.18), int(height * 0.13), (100, 150, 255), 88)
    od = ImageDraw.Draw(canvas)
    for i in range(8):
        angle = math.radians(i * 22.5)
        for d in range(int(min(width, height) * 0.15), int(min(width, height) * 0.55), max(1, int(min(width, height) * 0.05))):
            ex = width // 2 + int(d * math.cos(angle))
            ey = int(height * 0.5) + int(d * math.sin(angle))
            od.ellipse((ex-2, ey-2, ex+2, ey+2), fill=(150, 100, 255, 28))
    return canvas


def _tmpl_bg_beauty(width: int, height: int, preview_colors: list) -> Image.Image:
    """Deep rose-burgundy with pink luminescence — beauty aesthetic."""
    c1 = _hex_to_rgb(preview_colors[0]) if len(preview_colors) > 0 else (30, 6, 38)
    c2 = _hex_to_rgb(preview_colors[1]) if len(preview_colors) > 1 else (90, 18, 72)
    c3 = _hex_to_rgb(preview_colors[2]) if len(preview_colors) > 2 else (160, 35, 90)
    canvas = _tmpl_gradient_canvas(width, height, [c1, c2, c3], direction="diagonal")
    _tmpl_add_glow(canvas, int(width * 0.26), int(height * 0.36), int(width * 0.38), int(height * 0.32), (255, 140, 190), 55)
    _tmpl_add_glow(canvas, int(width * 0.74), int(height * 0.56), int(width * 0.30), int(height * 0.28), (255, 200, 150), 40)
    od = ImageDraw.Draw(canvas)
    random.seed("beauty-tmpl-v3")
    for _ in range(20):
        bx, by = random.randint(0, width), random.randint(0, height)
        br = random.randint(3, 14)
        od.ellipse((bx-br, by-br, bx+br, by+br), fill=(255, 180, 220, random.randint(12, 28)))
    return canvas


def _tmpl_bg_sports(width: int, height: int, preview_colors: list) -> Image.Image:
    """Dark diagonal with yellow energy bursts — sports / high energy."""
    c1 = _hex_to_rgb(preview_colors[0]) if len(preview_colors) > 0 else (12, 9, 26)
    c2 = _hex_to_rgb(preview_colors[1]) if len(preview_colors) > 1 else (55, 9, 100)
    c3 = _hex_to_rgb(preview_colors[2]) if len(preview_colors) > 2 else (130, 24, 72)
    canvas = _tmpl_gradient_canvas(width, height, [c1, c2, c3], direction="diagonal")
    _tmpl_add_glow(canvas, int(width * 0.62), int(height * 0.45), int(width * 0.42), int(height * 0.60), (255, 200, 0), 55)
    _tmpl_add_glow(canvas, int(width * 0.58), int(height * 0.40), int(width * 0.18), int(height * 0.22), (255, 230, 80), 70)
    od = ImageDraw.Draw(canvas)
    random.seed("sports-tmpl-v3")
    for _ in range(16):
        sx1 = random.randint(0, width)
        sy1 = random.randint(0, height)
        od.line([(sx1, sy1), (sx1 + random.randint(int(width*0.06), int(width*0.20)), sy1 - random.randint(2, 12))],
                fill=(255, 230, 50, random.randint(18, 42)), width=1)
    return canvas


def _tmpl_bg_corporate(width: int, height: int, preview_colors: list) -> Image.Image:
    """Professional navy gradient — corporate / B2B."""
    c1 = _hex_to_rgb(preview_colors[0]) if len(preview_colors) > 0 else (4, 16, 36)
    c2 = _hex_to_rgb(preview_colors[1]) if len(preview_colors) > 1 else (10, 72, 132)
    c3 = _hex_to_rgb(preview_colors[2]) if len(preview_colors) > 2 else (20, 118, 180)
    canvas = _tmpl_gradient_canvas(width, height, [c1, c2, c3], direction="diagonal")
    _tmpl_add_glow(canvas, int(width * 0.65), int(height * 0.50), int(width * 0.35), int(height * 0.70), (82, 197, 255), 40)
    od = ImageDraw.Draw(canvas)
    step = max(44, width // 18)
    for x in range(-height, width + step, step):
        od.line([(x, 0), (x + height, height)], fill=(255, 255, 255, 8), width=1)
    return canvas


def _tmpl_bg_premium_hero(width: int, height: int, preview_colors: list) -> Image.Image:
    """Premium Hero — diagonal dark-to-electric-blue sweep, vivid glow, accent streaks."""
    c1 = _hex_to_rgb(preview_colors[0]) if len(preview_colors) > 0 else (3, 5, 18)
    c2 = _hex_to_rgb(preview_colors[1]) if len(preview_colors) > 1 else (5, 14, 50)
    c3 = _hex_to_rgb(preview_colors[2]) if len(preview_colors) > 2 else (8, 30, 95)
    # Diagonal gradient: very dark top-left → electric blue bottom-right
    sw, sh = 480, max(300, int(480 * height / width))
    base = Image.new("RGB", (sw, sh))
    px = base.load()
    for y in range(sh):
        for x in range(sw):
            t = min(1.0, max(0.0, x / sw * 0.55 + y / sh * 0.45))
            seg = min(int(t * 2), 1)
            lt = t * 2 - seg
            cs = [c1, c2, c3]
            px[x, y] = tuple(int(cs[seg][i] + (cs[min(seg+1, 2)][i] - cs[seg][i]) * lt) for i in range(3))
    canvas = base.resize((width, height), Image.Resampling.BICUBIC).convert("RGBA")
    # Strong right-side product glow — two layers for depth
    _tmpl_add_glow(canvas, int(width * 0.72), int(height * 0.45), int(width * 0.52), int(height * 0.42), (0, 75, 220), 84)
    _tmpl_add_glow(canvas, int(width * 0.74), int(height * 0.40), int(width * 0.28), int(height * 0.22), (0, 165, 255), 98)
    _tmpl_add_glow(canvas, int(width * 0.76), int(height * 0.38), int(width * 0.12), int(height * 0.10), (80, 200, 255), 90)
    # Subtle left ambient for person zone
    _tmpl_add_glow(canvas, int(width * 0.20), int(height * 0.52), int(width * 0.34), int(height * 0.36), (0, 28, 110), 35)
    od = ImageDraw.Draw(canvas)
    # Diagonal light sweep from upper-right — gives depth + dimension
    for i in range(4):
        ox = int(width * (0.58 + i * 0.09))
        ex = int(width * (1.10 + i * 0.06))
        od.line([(ox, 0), (ex, height)], fill=(0, 110, 255, max(3, 15 - i * 4)), width=max(1, width // 150))
    # Horizontal scan lines (subtle texture)
    for y in range(0, height, max(30, height // 28)):
        od.line([(0, y), (width, y)], fill=(255, 255, 255, 5), width=1)
    return canvas


def _tmpl_bg_influencer_split(width: int, height: int, preview_colors: list) -> Image.Image:
    """Influencer Split — near-black left (portrait) / vivid electric-blue right (product)."""
    c_dark = _hex_to_rgb(preview_colors[0]) if len(preview_colors) > 0 else (3, 4, 14)
    c_mid  = _hex_to_rgb(preview_colors[1]) if len(preview_colors) > 1 else (5, 16, 52)
    c_blue = _hex_to_rgb(preview_colors[2]) if len(preview_colors) > 2 else (8, 40, 125)
    # Horizontal split: dark left, electric blue right
    sw, sh = 480, max(300, int(480 * height / width))
    base = Image.new("RGB", (sw, sh))
    px = base.load()
    for y in range(sh):
        for x in range(sw):
            tx, ty = x / sw, y / sh
            if tx < 0.47:
                t = tx / 0.47
                px[x, y] = tuple(int(c_dark[i] + (c_mid[i] - c_dark[i]) * (t * 0.45 + ty * 0.12)) for i in range(3))
            else:
                t = (tx - 0.47) / 0.53
                px[x, y] = tuple(int(c_mid[i] + (c_blue[i] - c_mid[i]) * t) for i in range(3))
    canvas = base.resize((width, height), Image.Resampling.BICUBIC).convert("RGBA")
    # Portrait zone: soft circular ambient (left)
    _tmpl_add_glow(canvas, int(width * 0.26), int(height * 0.43), int(width * 0.32), int(height * 0.28), (0, 50, 165), 50)
    # Product zone: layered blue glow (right)
    _tmpl_add_glow(canvas, int(width * 0.74), int(height * 0.42), int(width * 0.46), int(height * 0.38), (0, 95, 240), 78)
    _tmpl_add_glow(canvas, int(width * 0.76), int(height * 0.38), int(width * 0.22), int(height * 0.17), (0, 178, 255), 92)
    od = ImageDraw.Draw(canvas)
    # Diagonal split accent line at center
    sp = int(width * 0.47)
    doff = int(height * 0.06)
    od.line([(sp + doff, 0), (sp - doff, height)], fill=(0, 130, 255, 30), width=max(2, width // 200))
    for y in range(0, height, max(28, height // 30)):
        od.line([(0, y), (width, y)], fill=(255, 255, 255, 4), width=1)
    return canvas


def _tmpl_bg_futuristic(width: int, height: int, preview_colors: list) -> Image.Image:
    """Futuristic Launch — near-black base, layered energy core, particle field."""
    c1 = _hex_to_rgb(preview_colors[0]) if len(preview_colors) > 0 else (1, 2, 10)
    c2 = _hex_to_rgb(preview_colors[1]) if len(preview_colors) > 1 else (3, 7, 28)
    c3 = _hex_to_rgb(preview_colors[2]) if len(preview_colors) > 2 else (4, 14, 52)
    canvas = _tmpl_gradient_canvas(width, height, [c1, c2, c3])
    # Layered energy core — three concentric pulses getting brighter inward
    cx, cy = width // 2, int(height * 0.51)
    _tmpl_add_glow(canvas, cx, cy, int(width * 0.56), int(height * 0.46), (0, 50, 165), 80)
    _tmpl_add_glow(canvas, cx, cy, int(width * 0.34), int(height * 0.28), (0, 120, 245), 100)
    _tmpl_add_glow(canvas, cx, cy, int(width * 0.15), int(height * 0.12), (0, 205, 255), 108)
    od = ImageDraw.Draw(canvas)
    # Particle / star field
    random.seed("futuristic-bg-v4")
    for _ in range(55):
        px2, py2 = random.randint(0, width), random.randint(0, height)
        pr = random.randint(1, 3)
        od.ellipse((px2-pr, py2-pr, px2+pr, py2+pr), fill=(160, 215, 255, random.randint(50, 140)))
    # Scan lines
    for y in range(0, height, max(28, height // 30)):
        od.line([(0, y), (width, y)], fill=(255, 255, 255, 5), width=1)
    return canvas


# ── Image placement helpers ───────────────────────────────────────────────────

def _tmpl_place_fill(canvas: Image.Image, img: Image.Image, x: int, y: int, w: int, h: int,
                     fade_right: bool = False, fade_left: bool = False, fade_amount: float = 0.25) -> None:
    """
    Place person image in zone.  Scales to fill zone height so the full figure is visible.
    If the image is a close-up (nearly square, e.g. headshot) we fall back to contain-width
    so the face doesn't become a wall of pixels.  Edge-fade blends subject into background.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    sw, sh = img.size

    # Primary: scale to fill zone height (shows full figure from head to toe)
    scale_h = h / max(1, sh)
    nw_h = max(1, int(sw * scale_h))

    # If height-fill would overflow zone width by more than 40%, the image is likely a
    # close-up headshot.  Switch to contain-width scaling instead.
    if nw_h > w * 1.4:
        scale = w / max(1, sw)
        nw = w
        nh = max(1, int(sh * scale))
        # For headshots: position slightly above center so the face stays visible
        oy = y + max(0, int((h - nh) * 0.15))
    else:
        scale = scale_h
        nw = nw_h
        nh = h
        oy = y + h - nh          # bottom-anchor — ground contact

    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    ox = x + (w - nw) // 2

    if fade_right or fade_left:
        arr = np.array(resized.getchannel("A"), dtype=np.float32)
        fade_w = int(nw * fade_amount)
        if fade_right:
            for i in range(fade_w):
                t = i / max(1, fade_w - 1)
                arr[:, min(nw - 1, nw - fade_w + i)] = np.minimum(
                    arr[:, min(nw - 1, nw - fade_w + i)], 255.0 * (1.0 - t * t))
        if fade_left:
            for i in range(fade_w):
                t = i / max(1, fade_w - 1)
                arr[:, max(0, fade_w - 1 - i)] = np.minimum(
                    arr[:, max(0, fade_w - 1 - i)], 255.0 * (1.0 - t * t))
        r, g, b, _ = resized.split()
        resized = Image.merge("RGBA", (r, g, b, Image.fromarray(arr.astype(np.uint8))))

    paste_x, paste_y = max(0, ox), max(0, oy)
    crop_x, crop_y = max(0, -ox), max(0, -oy)
    clip_w = min(nw - crop_x, canvas.width - paste_x)
    clip_h = min(nh - crop_y, canvas.height - paste_y)
    if clip_w > 0 and clip_h > 0:
        canvas.alpha_composite(resized.crop((crop_x, crop_y, crop_x + clip_w, crop_y + clip_h)), (paste_x, paste_y))


def _tmpl_place_product(canvas: Image.Image, product: Image.Image, cx: int, cy: int,
                        target_h: int, glow_rgb: tuple, glow_alpha: int = 55) -> None:
    """
    Place product centered at (cx, cy) with soft glow and drop shadow.
    - If the product has a transparent cutout: placed directly with accent glow.
    - If it has a solid background: wrapped in a dark rounded frame so it looks
      intentionally styled rather than pasted.
    """
    if product.mode != "RGBA":
        product = product.convert("RGBA")

    has_cutout = _alpha_has_cutout(product)

    sw, sh = product.size
    nw = max(1, int(sw * target_h / max(1, sh)))
    resized = product.resize((nw, target_h), Image.Resampling.LANCZOS)
    px, py = cx - nw // 2, cy - target_h // 2

    # Glow behind product
    gw, gh = int(nw * 2.0), int(target_h * 1.6)
    gimg = Image.new("RGBA", (max(4, gw), max(4, gh)), (0, 0, 0, 0))
    ImageDraw.Draw(gimg).ellipse((0, 0, gw, gh), fill=(*glow_rgb, glow_alpha))
    gimg = gimg.filter(ImageFilter.GaussianBlur(max(gw, gh) // 4))
    canvas.alpha_composite(gimg, (max(0, cx - gw // 2), max(0, cy - gh // 2 + target_h // 5)))

    if has_cutout:
        # Clean cutout — place directly with drop shadow
        simg = Image.new("RGBA", (nw + 20, target_h + 20), (0, 0, 0, 0))
        ImageDraw.Draw(simg).ellipse((6, target_h - 14, nw + 14, target_h + 18), fill=(0, 0, 0, 70))
        simg = simg.filter(ImageFilter.GaussianBlur(10))
        canvas.alpha_composite(simg, (max(0, px - 10), max(0, py - 10)))
        canvas.alpha_composite(resized, (max(0, px), max(0, py)))
    else:
        # No cutout — wrap in a styled dark rounded frame
        pad = max(10, target_h // 18)
        frame_w, frame_h = nw + pad * 2, target_h + pad * 2
        frame = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
        fd = ImageDraw.Draw(frame)
        radius = max(16, min(frame_w, frame_h) // 8)
        # Dark semi-transparent frame backing
        _draw_round_rect(fd, (0, 0, frame_w, frame_h), radius,
                         fill=(10, 12, 22, 210), outline=(*glow_rgb, 130), width=max(2, nw // 80))
        # Thin inner highlight line
        _draw_round_rect(fd, (3, 3, frame_w - 3, frame_h - 3), max(12, radius - 4),
                         fill=None, outline=(255, 255, 255, 28), width=1)
        # Product image with rounded clip
        inner = resized.convert("RGB").convert("RGBA")
        mask = Image.new("L", (nw, target_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, nw, target_h), radius=max(10, radius - 6), fill=255)
        inner.putalpha(mask)
        frame.alpha_composite(inner, (pad, pad))
        # Drop shadow for the whole frame
        simg = Image.new("RGBA", (frame_w + 24, frame_h + 24), (0, 0, 0, 0))
        ImageDraw.Draw(simg).rounded_rectangle((8, 12, frame_w + 16, frame_h + 20),
                                               radius=radius, fill=(0, 0, 0, 85))
        simg = simg.filter(ImageFilter.GaussianBlur(14))
        fpx = cx - frame_w // 2
        fpy = cy - frame_h // 2
        canvas.alpha_composite(simg, (max(0, fpx - 12), max(0, fpy - 12)))
        canvas.alpha_composite(frame, (max(0, fpx), max(0, fpy)))


def _tmpl_circular_portrait(person: Image.Image, size: int) -> Image.Image:
    """Crop + mask person image into a circular portrait of the given pixel diameter."""
    if person.mode != "RGBA":
        person = person.convert("RGBA")
    sw, sh = person.size
    # Scale so the shorter dimension fills the circle
    scale = size / min(sw, sh)
    nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
    resized = person.resize((nw, nh), Image.Resampling.LANCZOS)
    # Center-crop: slight upward offset so faces aren't cut at chin
    ox = (nw - size) // 2
    oy = max(0, int((nh - size) * 0.18))
    oy = min(oy, nh - size)
    cropped = resized.crop((ox, oy, ox + size, oy + size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(cropped.convert("RGBA"), (0, 0), mask)
    return result


# ── Text renderers ────────────────────────────────────────────────────────────

def _tmpl_draw_top_band(canvas: Image.Image, brand: str, headline: str, subheadline: str,
                        cta: str, accent_rgb: tuple, band_h: int) -> None:
    """Full-width top text band: gradient scrim → brand chip → headline → sub."""
    width = canvas.width
    scrim = Image.new("RGBA", (width, band_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    for i in range(band_h):
        t = 1.0 - (i / max(1, band_h - 1)) * 0.65
        sd.line([(0, i), (width, i)], fill=(0, 0, 0, int(200 * t)), width=1)
    canvas.alpha_composite(scrim)

    draw = ImageDraw.Draw(canvas)
    pad = max(24, width // 36)
    cy = max(16, band_h // 9)

    if brand:
        chip_font = _safe_font(max(13, width // 62), bold=True)
        chip_text = brand.upper()[:24]
        tw, th = _text_wh(draw, chip_text, chip_font)
        chip_w, chip_h = tw + 28, th + 12
        _draw_round_rect(draw, (pad, cy, pad + chip_w, cy + chip_h),
                         radius=chip_h // 2, fill=(*accent_rgb, 235),
                         outline=(255, 255, 255, 80), width=1)
        draw.text((pad + 14, cy + 5), chip_text, font=chip_font, fill=(0, 0, 0, 255))
        cy += chip_h + max(8, band_h // 14)

    h_font = _safe_font(max(30, int(width * 0.060)), bold=True)
    h_text = (headline or "YOUR HEADLINE").upper()
    lines = _wrap_lines(draw, h_text, h_font, max_width=int(width * 0.84), max_lines=2)
    for line in lines:
        draw.text((pad + 2, cy + 2), line, font=h_font, fill=(0, 0, 0, 120))
        draw.text((pad, cy), line, font=h_font, fill=(255, 255, 255, 255))
        cy += _text_wh(draw, line, h_font)[1] + max(3, band_h // 22)

    if subheadline:
        sub_font = _safe_font(max(15, int(width * 0.021)), bold=False)
        draw.text((pad + 1, cy + 1), subheadline, font=sub_font, fill=(0, 0, 0, 100))
        draw.text((pad, cy), subheadline, font=sub_font, fill=(*accent_rgb, 215))


def _tmpl_draw_side_text(canvas: Image.Image, x: int, y: int, w: int, h: int,
                         brand: str, headline: str, subheadline: str, cta: str,
                         accent_rgb: tuple, plan: str) -> None:
    """Side text panel: accent dot + brand → divider → headline → sub → CTA."""
    width, height = canvas.width, canvas.height
    scrim = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for i in range(w):
        t = max(0.0, min(1.0, i / max(1, w * 0.55)))
        ImageDraw.Draw(scrim).line([(i, 0), (i, h)], fill=(0, 0, 0, int(140 * (1.0 - t))), width=1)
    canvas.alpha_composite(scrim, (max(0, x), max(0, y)))

    draw = ImageDraw.Draw(canvas)
    pad = max(18, width // 42)
    cx, cy = x + pad, y + max(18, h // 10)

    if brand:
        b_font = _safe_font(max(12, width // 66), bold=True)
        b_text = brand.upper()[:28]
        dr2 = max(4, width // 165)
        draw.ellipse((cx, cy + 3, cx + dr2*2, cy + 3 + dr2*2), fill=(*accent_rgb, 240))
        draw.text((cx + dr2*2 + 8, cy), b_text, font=b_font, fill=(*accent_rgb, 215))
        cy += _text_wh(draw, b_text, b_font)[1] + max(8, h // 18)

    draw.line([(cx, cy), (cx + min(w // 3, 70), cy)], fill=(*accent_rgb, 180), width=max(2, width // 320))
    cy += max(10, h // 18)

    h_font = _safe_font(max(24, int(min(w * 1.2, height) * 0.068)), bold=True)
    h_text = headline or "Your Headline"
    for line in _wrap_lines(draw, h_text, h_font, max_width=w - pad * 2, max_lines=3):
        draw.text((cx + 2, cy + 2), line, font=h_font, fill=(0, 0, 0, 120))
        draw.text((cx, cy), line, font=h_font, fill=(255, 255, 255, 255))
        cy += _text_wh(draw, line, h_font)[1] + max(4, h // 30)
    cy += max(6, h // 22)

    if subheadline:
        sub_font = _safe_font(max(14, int(width * 0.019)), bold=False)
        for line in _wrap_lines(draw, subheadline, sub_font, max_width=w - pad * 2, max_lines=2):
            draw.text((cx, cy), line, font=sub_font, fill=(220, 220, 220, 200))
            cy += _text_wh(draw, line, sub_font)[1] + 4
        cy += max(8, h // 22)

    if cta and cy < y + h - 56:
        cta_font = _safe_font(max(14, int(width * 0.019)), bold=True)
        cta_text = cta[:26]
        tw, th = _text_wh(draw, cta_text, cta_font)
        btn_w, btn_h = tw + 40, th + 20
        btn_x = cx
        btn_y = min(cy, y + h - btn_h - 18)
        _draw_round_rect(draw, (btn_x + 3, btn_y + 4, btn_x + btn_w + 3, btn_y + btn_h + 4),
                         radius=btn_h // 2, fill=(0, 0, 0, 75))
        _draw_round_rect(draw, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h),
                         radius=btn_h // 2, fill=(*accent_rgb, 242),
                         outline=(255, 255, 255, 145), width=2)
        draw.text((btn_x + 20, btn_y + (btn_h - th) // 2 - 1), cta_text, font=cta_font, fill=(0, 0, 0, 255))


def _tmpl_draw_feature_bar(canvas: Image.Image, features: list, accent_rgb: tuple) -> None:
    """Professional bottom feature bar: icon circles + labels in N equal columns."""
    if not features:
        return
    width, height = canvas.size
    bar_h = max(88, height // 10)
    bar_y = height - bar_h
    bar = Image.new("RGBA", (width, bar_h), (0, 0, 0, 0))
    ImageDraw.Draw(bar).rectangle((0, 0, width, bar_h), fill=(0, 0, 0, 195))
    ImageDraw.Draw(bar).rectangle((0, 0, width, max(2, bar_h // 36)), fill=(*accent_rgb, 200))
    canvas.alpha_composite(bar, (0, bar_y))

    draw = ImageDraw.Draw(canvas)
    n = len(features)
    col_w = width // n
    icon_r = max(12, width // 65)
    text_font = _safe_font(max(13, width // 58), bold=True)

    for i, feat in enumerate(features):
        cx2 = col_w * i + col_w // 2
        icon_y2 = bar_y + max(10, bar_h // 8)
        draw.ellipse((cx2 - icon_r, icon_y2, cx2 + icon_r, icon_y2 + icon_r * 2),
                     outline=(*accent_rgb, 200), width=max(2, width // 310))
        dr3 = max(3, icon_r // 3)
        draw.ellipse((cx2 - dr3, icon_y2 + icon_r - dr3, cx2 + dr3, icon_y2 + icon_r + dr3),
                     fill=(*accent_rgb, 200))
        tf = text_font
        tw2, _ = _text_wh(draw, feat, tf)
        if tw2 > col_w - 10:
            tf = _safe_font(max(11, width // 70), bold=True)
            tw2, _ = _text_wh(draw, feat, tf)
        draw.text((cx2 - tw2 // 2, icon_y2 + icon_r * 2 + max(4, bar_h // 14)),
                  feat, font=tf, fill=(255, 255, 255, 228))
        if i < n - 1:
            draw.line([(col_w * (i+1), bar_y + bar_h//5), (col_w * (i+1), bar_y + bar_h - bar_h//5)],
                      fill=(255, 255, 255, 48), width=1)


def _tmpl_draw_benefit_pills(canvas: Image.Image, benefits: list, x: int, y: int, accent_rgb: tuple) -> None:
    """Vertically stacked pill badges — beauty / lifestyle template."""
    if not benefits:
        return
    draw = ImageDraw.Draw(canvas)
    font = _safe_font(max(13, canvas.width // 60), bold=True)
    cy2 = y
    for benefit in benefits:
        tw, th = _text_wh(draw, benefit, font)
        ppx, ppy = 18, 8
        bw, bh = tw + ppx * 2, th + ppy * 2
        pill = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        _draw_round_rect(ImageDraw.Draw(pill), (0, 0, bw, bh), radius=bh // 2,
                         fill=(*accent_rgb, 215), outline=(255, 255, 255, 120), width=1)
        canvas.alpha_composite(pill, (x, cy2))
        draw.text((x + ppx, cy2 + ppy - 1), benefit, font=font, fill=(0, 0, 0, 255))
        cy2 += bh + 10


def _tmpl_watermark(canvas: Image.Image, plan: str) -> None:
    if not (settings.watermark_free_plan and plan == "free"):
        return
    width, height = canvas.size
    draw = ImageDraw.Draw(canvas)
    font = _safe_font(max(13, width // 74), bold=True)
    text = "pixolab.online"
    tw, th = _text_wh(draw, text, font)
    wx = width - tw - max(14, width // 58)
    wy = height - th - max(12, height // 68)
    _draw_round_rect(draw, (wx - 10, wy - 6, wx + tw + 10, wy + th + 6), radius=12, fill=(0, 0, 0, 145))
    draw.text((wx, wy), text, font=font, fill=(255, 255, 255, 200))


# ── Layout-specific renderers ─────────────────────────────────────────────────

def _render_tmpl_tech_split(canvas: Image.Image, person: Image.Image, product: Image.Image,
                             data: dict, template: dict, plan: str) -> None:
    """Tech Product Launch — person left, product floating right, top text band, bottom feature bar."""
    width, height = canvas.size
    accent = _hex_to_rgb(template.get("accent_hex", "#00c8ff"))
    top_h = int(height * 0.22)

    _tmpl_place_fill(canvas, person, 0, 0, int(width * 0.57), height, fade_right=True, fade_amount=0.20)

    prod_cx = int(width * 0.75)
    prod_cy = int(height * 0.55)
    prod_h = int(height * 0.40)
    _tmpl_place_product(canvas, product, prod_cx, prod_cy, prod_h, accent, glow_alpha=65)

    _tmpl_draw_top_band(canvas, data.get("brand_name",""), data.get("headline",""),
                        data.get("subheadline",""), data.get("cta",""), accent, top_h)

    draw = ImageDraw.Draw(canvas)
    lx = int(width * 0.58)
    draw.line([(lx, top_h + 28), (lx, height - max(88, height//10) - 24)],
              fill=(*accent, 70), width=max(1, width // 370))

    features = [f for f in [data.get("feature1",""), data.get("feature2",""), data.get("feature3","")] if f.strip()]
    if features:
        _tmpl_draw_feature_bar(canvas, features, accent)
    _tmpl_watermark(canvas, plan)


def _render_tmpl_elegance(canvas: Image.Image, person: Image.Image, product: Image.Image,
                          data: dict, template: dict, plan: str) -> None:
    """Elegance Meets Power — person left, side text right, product floating bottom-right."""
    width, height = canvas.size
    accent = _hex_to_rgb(template.get("accent_hex", "#4da6ff"))

    _tmpl_place_fill(canvas, person, 0, 0, int(width * 0.50), height, fade_right=True, fade_amount=0.22)

    text_x = int(width * 0.53)
    text_w = width - text_x - int(width * 0.04)
    _tmpl_draw_side_text(canvas, text_x, int(height * 0.12), text_w, int(height * 0.65),
                         data.get("brand_name",""), data.get("headline",""),
                         data.get("subheadline",""), data.get("cta",""), accent, plan)

    _tmpl_place_product(canvas, product, int(width * 0.75), int(height * 0.82),
                        int(height * 0.26), accent, glow_alpha=55)

    draw = ImageDraw.Draw(canvas)
    div_y = int(height * 0.13)
    draw.line([(int(width*0.53), div_y), (width - int(width*0.04), div_y)],
              fill=(*accent, 95), width=max(1, height // 420))
    b_font = _safe_font(max(11, width // 70), bold=True)
    draw.text((int(width*0.04), int(height*0.04)), (data.get("brand_name","") or "BRAND").upper(),
              font=b_font, fill=(*accent, 175))
    _tmpl_watermark(canvas, plan)


def _render_tmpl_performance(canvas: Image.Image, person: Image.Image, product: Image.Image,
                              data: dict, template: dict, plan: str) -> None:
    """Built to Perform — centered person, top text band, product lower-right, feature bar."""
    width, height = canvas.size
    accent = _hex_to_rgb(template.get("accent_hex", "#00aaff"))
    top_h = int(height * 0.24)

    person_w = int(width * 0.68)
    _tmpl_place_fill(canvas, person, (width - person_w)//2, 0, person_w, height,
                     fade_right=True, fade_left=True, fade_amount=0.15)

    _tmpl_place_product(canvas, product, int(width*0.79), int(height*0.70),
                        int(height*0.30), accent, glow_alpha=62)

    _tmpl_draw_top_band(canvas, data.get("brand_name",""), data.get("headline",""),
                        data.get("subheadline",""), data.get("cta",""), accent, top_h)

    features = [f for f in [data.get("feature1",""), data.get("feature2",""), data.get("feature3","")] if f.strip()]
    if features:
        _tmpl_draw_feature_bar(canvas, features, accent)

    tagline = (data.get("bottom_tagline","") or "").strip()
    if tagline:
        bar_h = max(88, height//10) if features else 0
        draw = ImageDraw.Draw(canvas)
        tl_font = _safe_font(max(15, width//52), bold=True)
        tw, th = _text_wh(draw, tagline, tl_font)
        ty = height - bar_h - th - max(12, height//62)
        draw.text(((width - tw)//2 + 1, ty + 1), tagline, font=tl_font, fill=(0, 0, 0, 110))
        draw.text(((width - tw)//2, ty), tagline, font=tl_font, fill=(*accent, 215))
    _tmpl_watermark(canvas, plan)


def _render_tmpl_beauty(canvas: Image.Image, person: Image.Image, product: Image.Image,
                        data: dict, template: dict, plan: str) -> None:
    """Beauty & Glow — person left, product right-center, top text band, benefit pills."""
    width, height = canvas.size
    accent = _hex_to_rgb(template.get("accent_hex", "#ffaacc"))
    top_h = int(height * 0.20)

    _tmpl_place_fill(canvas, person, 0, 0, int(width*0.56), height, fade_right=True, fade_amount=0.22)

    _tmpl_place_product(canvas, product, int(width*0.76), int(height*0.55),
                        int(height*0.32), accent, glow_alpha=65)

    _tmpl_draw_top_band(canvas, data.get("brand_name",""), data.get("headline",""),
                        data.get("subheadline",""), data.get("cta",""), accent, top_h)

    benefits = [b for b in [data.get("benefit1",""), data.get("benefit2","")] if b.strip()]
    if benefits:
        _tmpl_draw_benefit_pills(canvas, benefits, int(width*0.57), int(height*0.72), accent)
    _tmpl_watermark(canvas, plan)


def _render_tmpl_sports(canvas: Image.Image, person: Image.Image, product: Image.Image,
                        data: dict, template: dict, plan: str) -> None:
    """Sports & Energy — person right, large left-side text, diagonal accent lines."""
    width, height = canvas.size
    accent = _hex_to_rgb(template.get("accent_hex", "#ffe632"))

    person_x = int(width * 0.48)
    _tmpl_place_fill(canvas, person, person_x, 0, width - person_x, height,
                     fade_left=True, fade_amount=0.20)

    _tmpl_draw_side_text(canvas, int(width*0.04), int(height*0.07), int(width*0.42),
                         int(height*0.86), data.get("brand_name",""), data.get("headline",""),
                         data.get("subheadline",""), data.get("cta",""), accent, plan)

    _tmpl_place_product(canvas, product, int(width*0.36), int(height*0.76),
                        int(height*0.32), accent, glow_alpha=60)

    draw = ImageDraw.Draw(canvas)
    lx2 = int(width * 0.46)
    offs = int(height * 0.07)
    draw.line([(lx2, 0), (lx2 - offs, height)], fill=(*accent, 90), width=max(2, width//210))
    draw.line([(lx2 + int(width*0.014), 0), (lx2 + int(width*0.014) - offs, height)],
              fill=(*accent, 38), width=max(1, width//420))
    _tmpl_watermark(canvas, plan)


def _render_tmpl_corporate(canvas: Image.Image, person: Image.Image, product: Image.Image,
                            data: dict, template: dict, plan: str) -> None:
    """Corporate Professional — left text, person right, vertical divider, small product."""
    width, height = canvas.size
    accent = _hex_to_rgb(template.get("accent_hex", "#52c5ff"))

    person_x = int(width * 0.62)
    _tmpl_place_fill(canvas, person, person_x, 0, width - person_x, height,
                     fade_left=True, fade_amount=0.28)

    _tmpl_draw_side_text(canvas, int(width*0.05), int(height*0.06), int(width*0.54),
                         int(height*0.88), data.get("brand_name",""), data.get("headline",""),
                         data.get("subheadline",""), data.get("cta",""), accent, plan)

    _tmpl_place_product(canvas, product, int(width*0.52), int(height*0.66),
                        int(height*0.38), accent, glow_alpha=50)

    draw = ImageDraw.Draw(canvas)
    div_x2 = int(width * 0.61)
    draw.line([(div_x2, int(height*0.08)), (div_x2, int(height*0.92))],
              fill=(*accent, 65), width=max(1, width//420))
    _tmpl_watermark(canvas, plan)


def _render_tmpl_premium_hero(canvas: Image.Image, person: Image.Image, product: Image.Image,
                              data: dict, template: dict, plan: str) -> None:
    """Premium Hero — product is the hero on the right, influencer faded left, text left panel, feature bar."""
    width, height = canvas.size
    accent = _hex_to_rgb(template.get("accent_hex", "#00b4ff"))

    # Faded person on left — headshots become low-opacity BG elements
    if person.mode != "RGBA":
        person = person.convert("RGBA")
    pw, ph = person.size
    # Threshold 0.38: treats anything up to ~1:2.6 portrait ratio as a headshot.
    # Only very tall full-body images (e.g. 400×1100+) get the fill treatment.
    is_headshot = (pw / max(1, ph)) > 0.38

    if is_headshot:
        temp = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        _tmpl_place_fill(temp, person, -int(width * 0.05), 0, int(width * 0.54), height,
                         fade_right=True, fade_amount=0.32)
        arr = np.array(temp)
        arr[:, :, 3] = (arr[:, :, 3] * 0.32).astype(np.uint8)
        canvas.alpha_composite(Image.fromarray(arr))
    else:
        _tmpl_place_fill(canvas, person, -int(width * 0.03), 0, int(width * 0.55), height,
                         fade_right=True, fade_amount=0.28)

    # Product: hero right with strong glow  (reference: cx=760, cy=620, h=680 for 1080×1350)
    prod_cx = int(width * 0.704)
    prod_cy = int(height * 0.459)
    prod_h = int(height * 0.504)
    _tmpl_place_product(canvas, product, prod_cx, prod_cy, prod_h, accent, glow_alpha=90)

    # Left text panel scrim for readability
    scrim_w = int(width * 0.52)
    scrim = Image.new("RGBA", (scrim_w, height), (0, 0, 0, 0))
    for i in range(scrim_w):
        t = max(0.0, 1.0 - (i / max(1, scrim_w * 0.68)))
        ImageDraw.Draw(scrim).line([(i, 0), (i, height)], fill=(0, 0, 0, int(165 * t)), width=1)
    canvas.alpha_composite(scrim, (0, 0))

    draw = ImageDraw.Draw(canvas)
    pad_x = max(48, int(width * 0.065))
    cy = max(48, int(height * 0.052))

    # Brand chip
    if data.get("brand_name"):
        b_font = _safe_font(max(13, int(width * 0.017)), bold=True)
        b_text = data["brand_name"].upper()[:22]
        tw, th = _text_wh(draw, b_text, b_font)
        chip_w, chip_h = tw + 28, th + 14
        _draw_round_rect(draw, (pad_x, cy, pad_x + chip_w, cy + chip_h),
                         radius=chip_h // 2, fill=(*accent, 230), outline=(255, 255, 255, 80), width=1)
        draw.text((pad_x + 14, cy + 6), b_text, font=b_font, fill=(0, 0, 0, 255))
        cy += chip_h + max(16, int(height * 0.022))

    # Accent divider
    draw.line([(pad_x, cy), (pad_x + int(width * 0.14), cy)],
              fill=(*accent, 200), width=max(2, height // 400))
    cy += max(18, int(height * 0.022))

    # Headline
    h_text = (data.get("headline") or "YOUR HEADLINE").upper()
    h_font = _safe_font(max(34, int(width * 0.072)), bold=True)
    max_tw = int(width * 0.44)
    for line in _wrap_lines(draw, h_text, h_font, max_width=max_tw, max_lines=3):
        draw.text((pad_x + 2, cy + 2), line, font=h_font, fill=(0, 0, 0, 130))
        draw.text((pad_x, cy), line, font=h_font, fill=(255, 255, 255, 255))
        cy += _text_wh(draw, line, h_font)[1] + max(5, int(height * 0.006))
    cy += max(18, int(height * 0.020))

    # Tagline
    if data.get("subheadline"):
        sub_font = _safe_font(max(17, int(width * 0.024)), bold=False)
        for line in _wrap_lines(draw, data["subheadline"], sub_font, max_width=max_tw, max_lines=2):
            draw.text((pad_x, cy), line, font=sub_font, fill=(*accent, 215))
            cy += _text_wh(draw, line, sub_font)[1] + 4
        cy += max(18, int(height * 0.020))

    # CTA button
    if data.get("cta"):
        cta_font = _safe_font(max(15, int(width * 0.020)), bold=True)
        cta_text = data["cta"][:28]
        tw2, th2 = _text_wh(draw, cta_text, cta_font)
        btn_w, btn_h = tw2 + 52, th2 + 24
        feats = [f for f in [data.get("feature1",""), data.get("feature2",""), data.get("feature3","")] if f and f.strip()]
        bar_offset = max(88, height // 10) + 18 if feats else 18
        btn_x, btn_y = pad_x, min(cy, height - bar_offset - btn_h)
        _draw_round_rect(draw, (btn_x + 3, btn_y + 4, btn_x + btn_w + 3, btn_y + btn_h + 4),
                         radius=btn_h // 2, fill=(0, 0, 0, 90))
        _draw_round_rect(draw, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h),
                         radius=btn_h // 2, fill=(*accent, 245), outline=(255, 255, 255, 140), width=2)
        draw.text((btn_x + 26, btn_y + (btn_h - th2) // 2), cta_text, font=cta_font, fill=(0, 0, 0, 255))

    feats = [f for f in [data.get("feature1",""), data.get("feature2",""), data.get("feature3","")] if f and f.strip()]
    if feats:
        _tmpl_draw_feature_bar(canvas, feats, accent)
    _tmpl_watermark(canvas, plan)


def _render_tmpl_influencer_split(canvas: Image.Image, person: Image.Image, product: Image.Image,
                                   data: dict, template: dict, plan: str) -> None:
    """Influencer Split — circular portrait left, product right, brand top-center, text bottom-center."""
    width, height = canvas.size
    accent = _hex_to_rgb(template.get("accent_hex", "#00b4ff"))

    if person.mode != "RGBA":
        person = person.convert("RGBA")
    pw, ph = person.size
    # Treat anything up to ~1:2.8 aspect ratio as a portrait/headshot
    # (only very tall full-body images, e.g. 400×1120+, fall through to fill)
    is_headshot = (pw / max(1, ph)) > 0.35

    # LEFT: circular portrait for headshots, faded full-body otherwise
    circle_size = int(min(width * 0.390, height * 0.308))  # ~420 px at 1080×1350
    portrait_cx = int(width * 0.258)   # ~278
    portrait_cy = int(height * 0.418)  # ~564

    if is_headshot:
        portrait = _tmpl_circular_portrait(person, circle_size)
        # Soft background plate behind portrait (glow aura)
        _tmpl_add_glow(canvas, portrait_cx, portrait_cy,
                       int(circle_size * 0.92), int(circle_size * 0.92), (0, 75, 200), 65)
        # Dark drop shadow
        shad = Image.new("RGBA", (circle_size + 28, circle_size + 28), (0, 0, 0, 0))
        ImageDraw.Draw(shad).ellipse((0, 0, circle_size + 28, circle_size + 28), fill=(0, 0, 0, 100))
        shad = shad.filter(ImageFilter.GaussianBlur(12))
        canvas.alpha_composite(shad, (portrait_cx - circle_size // 2 - 14, portrait_cy - circle_size // 2 - 14))
        # Inner solid accent ring
        ring = Image.new("RGBA", (circle_size + 18, circle_size + 18), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((0, 0, circle_size + 18, circle_size + 18),
                                     outline=(*accent, 230), width=max(4, circle_size // 78))
        canvas.alpha_composite(ring, (portrait_cx - circle_size // 2 - 9, portrait_cy - circle_size // 2 - 9))
        # Outer halo ring (wider, more transparent)
        ring2 = Image.new("RGBA", (circle_size + 44, circle_size + 44), (0, 0, 0, 0))
        ImageDraw.Draw(ring2).ellipse((0, 0, circle_size + 44, circle_size + 44),
                                      outline=(*accent, 90), width=max(2, circle_size // 140))
        canvas.alpha_composite(ring2, (portrait_cx - circle_size // 2 - 22, portrait_cy - circle_size // 2 - 22))
        # Portrait itself
        canvas.alpha_composite(portrait, (portrait_cx - circle_size // 2, portrait_cy - circle_size // 2))
    else:
        _tmpl_place_fill(canvas, person, 0, 0, int(width * 0.44), height, fade_right=True, fade_amount=0.22)

    # RIGHT: product
    prod_cx = int(width * 0.714)
    prod_cy = int(height * 0.400)
    prod_h = int(height * 0.481)
    _tmpl_place_product(canvas, product, prod_cx, prod_cy, prod_h, accent, glow_alpha=80)

    draw = ImageDraw.Draw(canvas)

    # Brand: top-center with accent underline
    top_cy = max(28, int(height * 0.038))
    if data.get("brand_name"):
        br_font = _safe_font(max(14, int(width * 0.018)), bold=True)
        br_text = data["brand_name"].upper()[:26]
        tw, th = _text_wh(draw, br_text, br_font)
        draw.text(((width - tw) // 2, top_cy), br_text, font=br_font, fill=(*accent, 230))
        top_cy += th + 8
        ul_w = tw + 44
        draw.line([((width - ul_w) // 2, top_cy), ((width + ul_w) // 2, top_cy)],
                  fill=(*accent, 160), width=max(2, height // 500))

    # Bottom scrim for text readability
    feats = [f for f in [data.get("feature1",""), data.get("feature2",""), data.get("feature3","")] if f and f.strip()]
    bar_h_px = max(88, height // 10) if feats else 0
    scrim_h = int(height * 0.30)
    scrim = Image.new("RGBA", (width, scrim_h), (0, 0, 0, 0))
    for i in range(scrim_h):
        t = i / max(1, scrim_h - 1)
        ImageDraw.Draw(scrim).line([(0, i), (width, i)], fill=(0, 0, 0, int(185 * t * t)), width=1)
    canvas.alpha_composite(scrim, (0, height - scrim_h))

    cy = int(height * 0.722)

    # Headline — centered
    h_text = (data.get("headline") or "YOUR HEADLINE").upper()
    h_font = _safe_font(max(30, int(width * 0.056)), bold=True)
    for line in _wrap_lines(draw, h_text, h_font, max_width=int(width * 0.80), max_lines=2):
        tw2, th2 = _text_wh(draw, line, h_font)
        draw.text(((width - tw2) // 2 + 2, cy + 2), line, font=h_font, fill=(0, 0, 0, 130))
        draw.text(((width - tw2) // 2, cy), line, font=h_font, fill=(255, 255, 255, 255))
        cy += th2 + max(4, int(height * 0.005))
    cy += max(10, int(height * 0.010))

    # Tagline — centered
    if data.get("subheadline"):
        sub_font = _safe_font(max(15, int(width * 0.021)), bold=False)
        for line in _wrap_lines(draw, data["subheadline"], sub_font, max_width=int(width * 0.70), max_lines=2):
            tw3, th3 = _text_wh(draw, line, sub_font)
            draw.text(((width - tw3) // 2, cy), line, font=sub_font, fill=(*accent, 210))
            cy += th3 + 4
        cy += max(12, int(height * 0.010))

    # CTA — centered pill button
    if data.get("cta"):
        cta_font = _safe_font(max(15, int(width * 0.021)), bold=True)
        cta_text = data["cta"][:28]
        tw4, th4 = _text_wh(draw, cta_text, cta_font)
        btn_w, btn_h = tw4 + 60, th4 + 24
        btn_x = (width - btn_w) // 2
        btn_y = min(cy, height - bar_h_px - btn_h - 16)
        _draw_round_rect(draw, (btn_x + 3, btn_y + 4, btn_x + btn_w + 3, btn_y + btn_h + 4),
                         radius=btn_h // 2, fill=(0, 0, 0, 90))
        _draw_round_rect(draw, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h),
                         radius=btn_h // 2, fill=(*accent, 245), outline=(255, 255, 255, 130), width=2)
        draw.text((btn_x + 30, btn_y + (btn_h - th4) // 2), cta_text, font=cta_font, fill=(0, 0, 0, 255))

    if feats:
        _tmpl_draw_feature_bar(canvas, feats, accent)
    _tmpl_watermark(canvas, plan)


def _render_tmpl_futuristic(canvas: Image.Image, person: Image.Image, product: Image.Image,
                             data: dict, template: dict, plan: str) -> None:
    """Futuristic Product Launch — concentric rings, centered product, ghost influencer BG."""
    width, height = canvas.size
    accent = _hex_to_rgb(template.get("accent_hex", "#00bfff"))
    sx, sy = width / 1080, height / 1350  # scale factors from reference size

    # Person as ultra-faint background element
    if person.mode != "RGBA":
        person = person.convert("RGBA")
    temp = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    _tmpl_place_fill(temp, person, 0, 0, width, height)
    arr = np.array(temp)
    arr[:, :, 3] = (arr[:, :, 3] * 0.20).astype(np.uint8)
    canvas.alpha_composite(Image.fromarray(arr))

    # Concentric futuristic rings (scaled from 1080×1350 reference)
    ring_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring_layer)
    rw = max(3, int(5 * min(sx, sy)))
    # Outer ring — vivid cyan
    rd.ellipse((int(220*sx), int(380*sy), int(860*sx), int(1020*sy)),
               outline=(0, 190, 255, 175), width=rw)
    # Middle ring — white
    rd.ellipse((int(290*sx), int(450*sy), int(790*sx), int(950*sy)),
               outline=(200, 240, 255, 100), width=max(2, rw - 1))
    # Inner ring — cyan, softer
    rd.ellipse((int(360*sx), int(520*sy), int(720*sx), int(880*sy)),
               outline=(0, 190, 255, 80), width=max(2, rw - 1))
    # Tick marks on outer ring — 12 evenly spaced
    ring_cx, ring_cy = int(540*sx), int(700*sy)
    ring_rx, ring_ry = int(320*sx), int(320*sy)
    for i in range(12):
        angle = math.radians(i * 30 - 90)
        bx = ring_cx + int(ring_rx * math.cos(angle))
        by = ring_cy + int(ring_ry * math.sin(angle))
        ex = ring_cx + int((ring_rx + int(20*sx)) * math.cos(angle))
        ey = ring_cy + int((ring_ry + int(20*sy)) * math.sin(angle))
        rd.line([(bx, by), (ex, ey)], fill=(0, 190, 255, 150), width=max(2, int(3 * min(sx, sy))))
    canvas.alpha_composite(ring_layer)

    # Product: centered in ring  (reference: center at (540, 700), h=680)
    prod_h = int(height * 0.504)
    _tmpl_place_product(canvas, product, width // 2, int(height * 0.519), prod_h, accent, glow_alpha=85)

    draw = ImageDraw.Draw(canvas)

    # Brand: top-center
    top_cy = max(34, int(height * 0.040))
    if data.get("brand_name"):
        br_font = _safe_font(max(14, int(width * 0.019)), bold=True)
        br_text = data["brand_name"].upper()[:26]
        tw, th = _text_wh(draw, br_text, br_font)
        draw.text(((width - tw) // 2, top_cy), br_text, font=br_font, fill=(*accent, 230))
        top_cy += th + 8
        ul_w = tw + 40
        draw.line([((width - ul_w) // 2, top_cy), ((width + ul_w) // 2, top_cy)],
                  fill=(*accent, 170), width=max(2, height // 500))
        top_cy += max(14, int(height * 0.014))

    # Headline — centered below brand
    h_text = (data.get("headline") or "THE FUTURE IS NOW").upper()
    h_font = _safe_font(max(36, int(width * 0.068)), bold=True)
    for line in _wrap_lines(draw, h_text, h_font, max_width=int(width * 0.82), max_lines=2):
        tw2, th2 = _text_wh(draw, line, h_font)
        draw.text(((width - tw2) // 2 + 2, top_cy + 2), line, font=h_font, fill=(0, 0, 0, 120))
        draw.text(((width - tw2) // 2, top_cy), line, font=h_font, fill=(255, 255, 255, 255))
        top_cy += th2 + max(5, int(height * 0.005))

    # Tagline — centered
    if data.get("subheadline"):
        top_cy += max(8, int(height * 0.008))
        sub_font = _safe_font(max(15, int(width * 0.020)), bold=False)
        for line in _wrap_lines(draw, data["subheadline"], sub_font, max_width=int(width * 0.72), max_lines=2):
            tw3, th3 = _text_wh(draw, line, sub_font)
            draw.text(((width - tw3) // 2, top_cy), line, font=sub_font, fill=(*accent, 205))
            top_cy += th3 + 4

    # CTA button — below product  (reference rect: 390,1025 → 690,1105)
    if data.get("cta"):
        cta_font = _safe_font(max(15, int(width * 0.021)), bold=True)
        cta_text = data["cta"][:28]
        tw4, th4 = _text_wh(draw, cta_text, cta_font)
        btn_ref_y = int(1025 * sy)
        btn_ref_h = int(80 * sy)
        btn_w = int(300 * sx)
        btn_h = max(btn_ref_h, th4 + 24)
        btn_x = (width - btn_w) // 2
        feats = [f for f in [data.get("feature1",""), data.get("feature2",""), data.get("feature3","")] if f and f.strip()]
        bar_h_px = max(88, height // 10) if feats else 0
        btn_y = min(btn_ref_y, height - bar_h_px - btn_h - 12)
        _draw_round_rect(draw, (btn_x + 3, btn_y + 4, btn_x + btn_w + 3, btn_y + btn_h + 4),
                         radius=btn_h // 2, fill=(0, 0, 0, 90))
        _draw_round_rect(draw, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h),
                         radius=btn_h // 2, fill=(*accent, 245), outline=(255, 255, 255, 130), width=2)
        draw.text((btn_x + (btn_w - tw4) // 2, btn_y + (btn_h - th4) // 2),
                  cta_text, font=cta_font, fill=(0, 0, 0, 255))

    feats = [f for f in [data.get("feature1",""), data.get("feature2",""), data.get("feature3","")] if f and f.strip()]
    if feats:
        _tmpl_draw_feature_bar(canvas, feats, accent)
    _tmpl_watermark(canvas, plan)


# ── Layout dispatcher ─────────────────────────────────────────────────────────

_LAYOUT_BG_MAP = {
    "tech_split":        _tmpl_bg_tech,
    "performance_action": _tmpl_bg_performance,
    "elegance_centered": _tmpl_bg_elegance,
    "beauty_glow":       _tmpl_bg_beauty,
    "sports_dynamic":    _tmpl_bg_sports,
    "corporate_split":   _tmpl_bg_corporate,
    "premium_hero":      _tmpl_bg_premium_hero,
    "influencer_split":  _tmpl_bg_influencer_split,
    "futuristic_launch": _tmpl_bg_futuristic,
}

_LAYOUT_RENDER_MAP = {
    "tech_split":        _render_tmpl_tech_split,
    "performance_action": _render_tmpl_performance,
    "elegance_centered": _render_tmpl_elegance,
    "beauty_glow":       _render_tmpl_beauty,
    "sports_dynamic":    _render_tmpl_sports,
    "corporate_split":   _render_tmpl_corporate,
    "premium_hero":      _render_tmpl_premium_hero,
    "influencer_split":  _render_tmpl_influencer_split,
    "futuristic_launch": _render_tmpl_futuristic,
}


def _tech_dark_background(width: int, height: int, preview_colors: list) -> Image.Image:
    """Deep space-like dark background with blue tech lighting."""
    try:
        c1 = _hex_to_rgb(preview_colors[0]) if len(preview_colors) > 0 else (5, 6, 24)
        c2 = _hex_to_rgb(preview_colors[1]) if len(preview_colors) > 1 else (10, 20, 62)
    except Exception:
        c1, c2 = (5, 6, 24), (10, 20, 62)

    small_w, small_h = 360, max(220, int(360 * height / width))
    base = Image.new("RGB", (small_w, small_h), c1)
    px = base.load()
    for y in range(small_h):
        t = y / max(1, small_h - 1)
        col = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        for x in range(small_w):
            px[x, y] = col
    canvas = base.resize((width, height), Image.Resampling.BICUBIC).convert("RGBA")

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # Central tech glow (right-center area)
    glows = [
        (int(width * 0.65), int(height * 0.35), int(width * 0.55), int(height * 0.42), (0, 80, 180), 55),
        (int(width * 0.30), int(height * 0.70), int(width * 0.45), int(height * 0.36), (0, 40, 120), 35),
        (int(width * 0.80), int(height * 0.80), int(width * 0.34), int(height * 0.28), (30, 120, 255), 28),
    ]
    for gx, gy, gw, gh, col, alpha in glows:
        gimg = Image.new("RGBA", (gw, gh), (*col, 0))
        gd = ImageDraw.Draw(gimg)
        gd.ellipse((0, 0, gw, gh), fill=(*col, alpha))
        gimg = gimg.filter(ImageFilter.GaussianBlur(max(30, gw // 6)))
        overlay.alpha_composite(gimg, (gx - gw // 2, gy - gh // 2))

    # Subtle scan-line grid
    for y in range(0, height, max(38, height // 22)):
        od.line([(0, y), (width, y)], fill=(255, 255, 255, 8), width=1)

    overlay = overlay.filter(ImageFilter.GaussianBlur(0.5))
    return Image.alpha_composite(canvas, overlay)



def compose_from_template(
    person_path: "Optional[Path]",
    product_path: "Path",
    template_id: str,
    template_data: dict,
    plan: str = "free",
) -> "tuple[Path, dict]":
    """
    Generate a poster using a predefined template.
    person_path is optional — when None a transparent placeholder is used so
    all renderers work unchanged (the placeholder is invisible).
    """
    from .templates_config import TEMPLATE_MAP

    template = TEMPLATE_MAP.get(template_id)
    if not template:
        raise ValueError(f"Unknown template: {template_id}")

    style = template["style"]
    layout_id = template.get("layout", "tech_split")
    dims = template.get("dimensions", list(STYLE_DIMENSIONS.get(style, [1080, 1080])))
    width, height = int(dims[0]), int(dims[1])

    pipeline_meta: dict = {
        "width": width, "height": height, "mode": "template",
        "template_id": template_id, "used_background_removal": False,
        "used_groq": False, "used_hf_background": False,
        "used_ai_creative": False, "used_inpainting": False,
        "prompt": f"Template: {template['name']}",
    }

    print(f"[Template] START — id={template_id} layout={layout_id} size={width}x{height} person={'yes' if person_path else 'no'}")

    # Step 1: Load + BG removal
    product_raw = Image.open(product_path)

    if person_path:
        person_raw = Image.open(person_path)
    else:
        # No person uploaded — create a canvas-sized transparent placeholder.
        # All renderers treat this as "no influencer" and it renders invisible.
        person_raw = Image.new("RGBA", (int(width * 0.6), height), (0, 0, 0, 0))

    if settings.enable_background_removal:
        print("[Template] removing backgrounds...")
        person_processed = _try_remove_background(person_raw, "person") if person_path else person_raw
        product_processed = _try_remove_background(product_raw, "product")
        pipeline_meta["used_background_removal"] = bool(person_path)
        import gc as _gc
        _rembg_session.cache_clear()
        _gc.collect()
        print("[Template] backgrounds removed")
    else:
        person_processed = person_raw.convert("RGBA")
        product_processed = product_raw.convert("RGBA")

    # Step 2: Template-specific background
    print("[Template] generating background...")
    bg_fn = _LAYOUT_BG_MAP.get(layout_id, _tmpl_bg_tech)
    bg = bg_fn(width, height, template.get("preview_colors", []))

    # Step 3: Layout-specific render
    print("[Template] compositing layers...")
    canvas = bg.copy()
    render_fn = _LAYOUT_RENDER_MAP.get(layout_id, _render_tmpl_tech_split)
    render_fn(canvas, person_processed, product_processed, template_data, template, plan)

    # Step 4: Final polish + save
    out_name = f"pixolab_tmpl_{uuid.uuid4().hex}.png"
    out_path = settings.storage_dir / "results" / out_name
    _finalize_output(canvas.convert("RGB")).save(out_path, quality=96, optimize=True)
    print(f"[Template] DONE — {out_path.name}")
    return out_path, pipeline_meta
