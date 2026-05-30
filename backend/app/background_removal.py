"""
Background Removal Module

Handles removing backgrounds from product and person images with smart fallbacks.
Supports rembg (BiRefNet/isnet/U²-Net) as primary method with SAM2 fallback.
"""

import logging
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageFilter, ImageOps
import numpy as np

logger = logging.getLogger(__name__)

# Ordered list of rembg model names to try — best quality first.
# birefnet-general uses 800MB+ runtime RAM — skip it; u2net/isnet are sufficient.
_REMBG_MODEL_PREFERENCE = ["isnet-general-use", "u2net"]


def _rembg_model_cached(model_name: str) -> bool:
    """Return True only if the model ONNX file is already on disk."""
    from pathlib import Path
    return (Path.home() / ".u2net" / f"{model_name}.onnx").exists()


@lru_cache(maxsize=1)
def _get_rembg_session():
    """Return a cached rembg session using only pre-downloaded models.
    Never triggers a model download to avoid blocking user requests."""
    try:
        from rembg import new_session  # type: ignore
        for model in _REMBG_MODEL_PREFERENCE:
            if not _rembg_model_cached(model):
                continue  # skip ALL models not yet on disk
            try:
                session = new_session(model)
                logger.info(f"rembg session created with model: {model}")
                return session
            except Exception as exc:
                logger.warning(f"rembg model '{model}' failed: {exc}")
        logger.warning("No rembg model found on disk — background removal skipped")
        return None
    except ImportError:
        logger.warning("rembg not installed")
        return None


def refine_alpha_edges(img: Image.Image, blur_radius: float = 1.2) -> Image.Image:
    """
    Feather alpha channel edges to eliminate jagged cutout borders.
    Only modifies the transition zone (alpha 8–248); solid interior/exterior untouched.
    """
    if img.mode != "RGBA":
        return img.convert("RGBA")
    r, g, b, a = img.split()
    a_arr = np.array(a, dtype=np.float32)
    a_blurred = np.array(a.filter(ImageFilter.GaussianBlur(blur_radius)), dtype=np.float32)
    edge_mask = (a_arr > 8) & (a_arr < 248)
    result = a_arr.copy()
    result[edge_mask] = a_blurred[edge_mask]
    return Image.merge("RGBA", (r, g, b, Image.fromarray(result.astype(np.uint8))))


def remove_background_rembg(image: Image.Image) -> Image.Image:
    """
    Remove background using rembg (BiRefNet-general preferred, falls back to u2net).
    If no session is available, returns the original image unchanged.
    """
    try:
        from rembg import remove  # type: ignore

        session = _get_rembg_session()
        if session is None:
            # rembg unavailable or no model cached — return original without hanging
            logger.warning("rembg session unavailable, returning original image")
            return image.convert("RGBA")

        result = remove(image, session=session)
        result = result.convert("RGBA")
        return refine_alpha_edges(result)
    except ImportError:
        logger.warning("rembg not installed, skipping background removal")
        return image.convert("RGBA")
    except Exception as e:
        logger.error(f"rembg failed: {e}")
        return image.convert("RGBA")


def remove_background_sam2(image: Image.Image) -> Image.Image:
    """
    Remove background using SAM2 + Grounding DINO (fallback for complex images).
    More complex but better for difficult backgrounds.
    """
    try:
        # This is a placeholder. SAM2 integration is complex and requires more setup.
        # For now, we'll log that it's not available.
        logger.warning("SAM2 not implemented yet, falling back to rembg")
        return remove_background_rembg(image)
    except Exception as e:
        logger.error(f"SAM2 fallback failed: {e}")
        return image.convert("RGBA")


def _alpha_has_cutout(image: Image.Image) -> bool:
    """
    Check if the image has a meaningful alpha channel (transparent cutout).
    Returns True if >5% of image has alpha < 200 (meaningful transparency).
    """
    if image.mode != "RGBA":
        return False
    
    try:
        alpha = np.array(image.getchannel("A"))
        transparent_pixels = np.sum(alpha < 200)
        total_pixels = alpha.size
        cutout_ratio = transparent_pixels / total_pixels if total_pixels > 0 else 0
        
        has_cutout = cutout_ratio > 0.05  # >5% transparent
        logger.debug(f"Cutout detection: {cutout_ratio:.2%} transparent → {has_cutout}")
        return has_cutout
    except Exception as e:
        logger.error(f"Cutout detection failed: {e}")
        return False


def remove_background(
    image_path: Path | str,
    method: str = "rembg",
    kind: str = "product"
) -> Image.Image:
    """
    Remove background from an image with smart method selection and fallback.
    
    Args:
        image_path: Path to the image file
        method: "rembg" or "sam2" (rembg is default, faster)
        kind: "product" or "person" (for logging/debugging)
    
    Returns:
        PIL Image in RGBA mode with transparent background
    """
    try:
        # Open and validate image
        image = Image.open(image_path)
        
        if image.size[0] < 50 or image.size[1] < 50:
            logger.warning(f"Image too small ({image.size}), returning as-is")
            return image.convert("RGBA")

        # Cap to 800px max side — rembg inference is ~4× faster at 800px vs 1650px
        max_side = 800
        if max(image.size) > max_side:
            ratio = max_side / max(image.size)
            image = image.resize(
                (int(image.size[0] * ratio), int(image.size[1] * ratio)),
                Image.Resampling.LANCZOS,
            )

        logger.info(f"Removing background from {kind} image ({image.size})")
        
        # Try primary method
        if method == "sam2":
            result = remove_background_sam2(image)
        else:
            # Default to rembg
            result = remove_background_rembg(image)
        
        # Validate result
        if not _alpha_has_cutout(result):
            logger.warning(f"No meaningful cutout detected for {kind}, trying alternative method")
            if method == "rembg":
                result = remove_background_sam2(image)
            else:
                result = remove_background_rembg(image)
        
        logger.info(f"Background removed for {kind}: {result.mode} {result.size}")
        return result
        
    except Exception as e:
        logger.error(f"Background removal failed for {kind}: {e}")
        # Return image as-is with alpha channel
        return Image.open(image_path).convert("RGBA")


def enhance_transparency(image: Image.Image, threshold: int = 200) -> Image.Image:
    """
    Enhance transparency by making semi-transparent pixels fully transparent.
    Helps improve cutout quality by hardening soft edges.
    
    Args:
        image: RGBA image
        threshold: Alpha values below this become fully transparent
    
    Returns:
        Enhanced RGBA image
    """
    if image.mode != "RGBA":
        return image
    
    try:
        alpha = image.getchannel("A")
        # Binary threshold: pixels below threshold → fully transparent
        alpha_array = np.array(alpha)
        alpha_array[alpha_array < threshold] = 0
        alpha_array[alpha_array >= threshold] = 255
        
        enhanced = image.copy()
        enhanced.putalpha(Image.fromarray(alpha_array))
        return enhanced
    except Exception as e:
        logger.error(f"Transparency enhancement failed: {e}")
        return image


def smart_crop_transparent(image: Image.Image, padding: int = 10) -> Image.Image:
    """
    Crop image to bounding box of non-transparent content, with padding.
    Removes excess transparent areas.
    
    Args:
        image: RGBA image
        padding: Pixels to pad around the detected content
    
    Returns:
        Cropped RGBA image
    """
    if image.mode != "RGBA":
        return image
    
    try:
        # Find bounding box of non-transparent pixels
        alpha = image.getchannel("A")
        bbox = alpha.getbbox()
        
        if bbox is None:
            logger.warning("No non-transparent content found")
            return image
        
        # Add padding
        x1, y1, x2, y2 = bbox
        x1 = max(0, x1 - padding)
        y1 = max(0, y1 - padding)
        x2 = min(image.width, x2 + padding)
        y2 = min(image.height, y2 + padding)
        
        cropped = image.crop((x1, y1, x2, y2))
        logger.debug(f"Cropped from {image.size} to {cropped.size}")
        return cropped
    except Exception as e:
        logger.error(f"Smart crop failed: {e}")
        return image
