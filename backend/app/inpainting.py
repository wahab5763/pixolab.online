"""
Inpainting Module

Harmonizes the final composite poster using FLUX.1-Kontext-dev or SDXL inpainting.
Optional premium feature to improve lighting, shadows, and integration.
"""

import logging
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)


def harmonize_poster_with_inpainting(
    composite_image: Image.Image,
    prompt: str,
    model_id: str = "black-forest-labs/FLUX.1-Kontext-dev",
    hf_token: str = "",
    width: int = 1080,
    height: int = 1080
) -> Image.Image | None:
    """
    Use FLUX.1-Kontext-dev to harmonize the composited poster.
    Improves lighting, shadows, and visual integration without changing product/person identity.
    
    Args:
        composite_image: PIL Image of the composited poster
        prompt: Specific instruction for harmonization (include in instruction param)
        model_id: HF model ID (default: FLUX.1-Kontext-dev)
        hf_token: Hugging Face API token
        width, height: Output dimensions
    
    Returns:
        Harmonized PIL Image or None if inpainting failed/disabled
    """
    
    if not hf_token or not hf_token.strip():
        logger.warning("HF_TOKEN not available, skipping inpainting")
        return None
    
    if "FLUX.1-Kontext" not in model_id:
        logger.warning(f"Inpainting model {model_id} not optimized, skipping")
        return None
    
    try:
        from huggingface_hub import InferenceClient
        
        logger.info(f"Harmonizing poster with {model_id}")
        
        client = InferenceClient(api_key=hf_token)
        
        # The instruction should be clear about preserving identity
        instruction = (
            "Make this look like a premium professional advertisement poster. "
            "Keep the product exactly the same - do not change its appearance, label, or packaging. "
            "Keep the person's face, identity, and pose unchanged. "
            "Improve the overall lighting, shadows, reflections, background integration, and cinematic quality. "
            "Add depth and professional polish without altering any key elements. "
            "Do not add or change any text. Do not add watermarks or logos. "
            "Enhance only the visual harmony and professional quality of the scene."
        )
        
        # Use image-to-image with the instruction
        harmonized = client.image_to_image(
            composite_image.convert("RGB"),
            instruction=instruction,
            guidance_scale=7.5,
            num_inference_steps=28,
            model=model_id,
        )
        
        logger.info("Inpainting harmonization complete")
        return harmonized.convert("RGBA") if harmonized else None
        
    except ImportError:
        logger.warning("huggingface_hub not available")
        return None
    except Exception as e:
        logger.error(f"Inpainting failed: {e}")
        return None


def apply_smart_inpainting_mask(
    composite_image: Image.Image,
    product_bbox: tuple[int, int, int, int],
    person_bbox: tuple[int, int, int, int],
    preserve_ratio: float = 0.9
) -> Image.Image | None:
    """
    Create an inpainting mask that preserves product and person (core elements)
    but allows the model to improve the rest.
    
    Args:
        composite_image: Full composite image
        product_bbox: (x, y, w, h) of product area - preserve this
        person_bbox: (x, y, w, h) of person area - preserve this
        preserve_ratio: How much to preserve (0.9 = protect 90% of element area)
    
    Returns:
        Inpaint mask image or None
    """
    
    try:
        width, height = composite_image.size
        mask = Image.new("L", (width, height), 255)  # 255 = inpaint, 0 = preserve
        
        # Preserve product area with margin
        px, py, pw, ph = product_bbox
        margin = int(min(pw, ph) * (1 - preserve_ratio))
        mask.paste(0, (max(0, px + margin), max(0, py + margin), 
                       min(width, px + pw - margin), min(height, py + ph - margin)))
        
        # Preserve person area with margin
        prx, pry, prw, prh = person_bbox
        margin = int(min(prw, prh) * (1 - preserve_ratio))
        mask.paste(0, (max(0, prx + margin), max(0, pry + margin),
                       min(width, prx + prw - margin), min(height, pry + prh - margin)))
        
        logger.debug("Inpaint mask created with preserved regions")
        return mask
        
    except Exception as e:
        logger.error(f"Mask generation failed: {e}")
        return None


def should_use_inpainting(enable_inpainting: bool, plan: str) -> bool:
    """
    Determine if inpainting should be used based on settings and plan.
    Inpainting is optional and best for premium plans.
    """
    if not enable_inpainting:
        return False
    
    # Could restrict inpainting to premium plans only
    # if plan == "free":
    #     return False
    
    return True
