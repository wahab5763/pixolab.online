"""
Groq API Integration Module

Handles creative concept generation using Groq LLM.
Generates structured JSON with ad positioning, lighting, text suggestions, etc.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def initialize_groq_client(api_key: str):
    """Initialize and return Groq client. Can be called multiple times."""
    if not api_key or not api_key.strip():
        logger.warning("GROQ_API_KEY not configured")
        return None
    
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        logger.info("Groq client initialized successfully")
        return client
    except ImportError:
        logger.error("groq package not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Groq client: {e}")
        return None


def generate_ad_concept(
    groq_client,
    product_caption: str = "Premium product",
    person_caption: str = "Influencer/brand ambassador",
    brand_name: str = "",
    style: str = "instagram_ad",
    target_audience: str = "18-35 years old, fashion/lifestyle enthusiasts",
    user_headline: str = "",
    user_subheadline: str = "",
    user_cta: str = ""
) -> dict:
    """
    Generate creative ad concept using Groq LLM.
    
    Returns a JSON dict with:
    - visual_concept: Overall visual direction
    - background_prompt: Detailed background description for image generation
    - lighting_style: Specific lighting instructions
    - product_position: Where to place product (e.g., "center-right, large foreground")
    - person_position: Where to place person (e.g., "left, standing")
    - headline: Recommended headline (or use user's if provided)
    - subheadline: Recommended subheadline (or use user's if provided)
    - cta: Call-to-action text (or use user's if provided)
    - negative_prompt: What NOT to include in background
    """
    
    if not groq_client:
        logger.warning("Groq client not available, returning fallback concept")
        return _fallback_concept(style)
    
    # Build system prompt for art director role
    system_prompt = """You are an expert advertising art director and visual designer with 15+ years of experience in premium brand campaigns.

Your task is to analyze product, influencer, and brand details, then generate a detailed JSON creative brief.

IMPORTANT RULES:
1. Return ONLY valid JSON, nothing else
2. All fields must be strings
3. Be specific and visual in descriptions
4. Consider the target audience and style
5. Ensure person and product don't overlap in positioning
6. background_prompt should describe an empty space ready for asset placement
7. Avoid mentioning the product or person IN the background_prompt (they'll be composited separately)
8. negative_prompt should include common mistakes to avoid"""

    user_prompt = f"""Generate a premium advertising creative brief in JSON format.

INPUTS:
Product: {product_caption}
Brand: {brand_name or 'Not specified'}
Style: {style} (format: {_style_to_dimensions(style)})
Target Audience: {target_audience}
Person/Influencer: {person_caption}

User-provided text (if empty, generate suggestions):
- Headline: "{user_headline or '(suggest one)'}"
- Subheadline: "{user_subheadline or '(suggest one)'}"
- CTA: "{user_cta or '(suggest one)'}"

Return JSON with these exact fields:
{{
  "visual_concept": "Overall creative direction and mood",
  "background_prompt": "Detailed background only - no products, no people, emphasize space and lighting",
  "lighting_style": "Specific lighting (e.g., 'soft three-point lighting with rim light')",
  "product_position": "Specific placement (e.g., 'bottom-right, 35% of frame, large and dominant')",
  "person_position": "Specific placement (e.g., 'left side, 50% of frame, standing naturally')",
  "headline": "Compelling headline text",
  "subheadline": "Supporting text",
  "cta": "Call-to-action (e.g., 'Shop Now', 'Learn More')",
  "negative_prompt": "What to avoid in generation (misspelled words, distorted faces, etc.)"
}}"""

    try:
        logger.info("Generating creative concept with Groq")

        message = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1024,
            response_format={"type": "json_object"},
            timeout=8.0,
        )

        # Extract JSON from response
        response_text = message.choices[0].message.content
        logger.debug(f"Groq response: {response_text[:200]}...")
        
        concept = json.loads(response_text)
        logger.info("Creative concept generated successfully")
        return concept
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Groq JSON response: {e}")
        return _fallback_concept(style)
    except Exception as e:
        logger.error(f"Groq API call failed: {e}")
        return _fallback_concept(style)


def _style_to_dimensions(style: str) -> str:
    """Map style to dimensions string."""
    dims = {
        "instagram_ad": "1080x1080 square",
        "linkedin_post": "1200x627 landscape",
        "product_poster": "1080x1350 portrait",
        "brand_ambassador": "1080x1350 portrait",
        "youtube_thumbnail": "1280x720 landscape"
    }
    return dims.get(style, "1080x1080")


def _fallback_concept(style: str) -> dict:
    """
    Return a sensible fallback creative brief when Groq is unavailable.
    Ensures poster generation doesn't fail if API is down.
    """
    concepts = {
        "instagram_ad": {
            "visual_concept": "Vibrant, modern Instagram-ready aesthetic with warm gradients and polished studio feel",
            "background_prompt": "Vibrant lifestyle advertising background with warm cinematic gradient, polished modern studio lighting, premium social media feel. No people, no products, just beautiful empty space with soft spotlight",
            "lighting_style": "Warm three-point lighting with golden hour glow and soft shadows",
            "product_position": "Center-right, 40% of frame, large and dominant, floating on soft gradient",
            "person_position": "Left-center, 45% of frame, naturally posed",
            "headline": "Discover Premium Quality",
            "subheadline": "Experience the difference",
            "cta": "Shop Now",
            "negative_prompt": "blurry, low quality, distorted text, bad lighting, dark, unprofessional"
        },
        "product_poster": {
            "visual_concept": "Dramatic, cinematic product launch campaign with luxury retail feel and stage spotlight",
            "background_prompt": "Dramatic luxury product launch background with cinematic spotlight, high contrast lighting, premium retail stage. No products, no people, dramatic shadows and clean empty space",
            "lighting_style": "High-contrast spotlight with dramatic shadows and reflective surfaces",
            "product_position": "Center, 50% of frame, dramatic spotlight, hero product focus",
            "person_position": "Right side or background blur, supporting role",
            "headline": "Introducing. Premium.",
            "subheadline": "Innovation meets elegance",
            "cta": "Get It First",
            "negative_prompt": "blurry, low quality, distorted product, misspelled text, confusing composition"
        },
        "linkedin_post": {
            "visual_concept": "Professional, corporate, trust-building campaign with clean modern design",
            "background_prompt": "Professional corporate advertising background with navy blue and silver tones, clean modern technology feel, minimal design. No products, no people, just professional empty space",
            "lighting_style": "Clean professional lighting with subtle gradients and modern accents",
            "product_position": "Center-right, 35% of frame, professional presentation",
            "person_position": "Left, 40% of frame, professional attire",
            "headline": "Transform Your Business",
            "subheadline": "Enterprise solutions that drive results",
            "cta": "Learn More",
            "negative_prompt": "colorful, playful, casual, distorted, unprofessional, low quality"
        },
        "brand_ambassador": {
            "visual_concept": "Luxurious, editorial magazine-style campaign with aspirational premium lifestyle feel",
            "background_prompt": "Luxury editorial magazine background with warm premium tones, soft elegant lighting, aspirational lifestyle mood. No products, no people, just beautiful empty space",
            "lighting_style": "Soft warm lighting with gentle gradients and elegant shadows",
            "product_position": "Lower right, 30% of frame, elegant placement",
            "person_position": "Center-left, 55% of frame, glamorous pose",
            "headline": "Live Luxuriously",
            "subheadline": "Premium experiences await",
            "cta": "Explore",
            "negative_prompt": "cheap, low quality, distorted, amateur, harsh lighting, busy"
        },
        "youtube_thumbnail": {
            "visual_concept": "High-impact, bold, click-worthy thumbnail with strong contrast and energetic appeal",
            "background_prompt": "High-impact creator thumbnail background with bold energetic lighting, strong contrast, vibrant colors. No products, no people, just striking visual composition",
            "lighting_style": "Bold high-contrast lighting with vibrant colors and strong shadows",
            "product_position": "Center-right, 40% of frame, bold and attention-grabbing",
            "person_position": "Left, 45% of frame, energetic pose",
            "headline": "Don't Miss Out!",
            "subheadline": "Click to discover more",
            "cta": "Watch Now",
            "negative_prompt": "blurry, low quality, dull colors, confusing, misspelled, distracting"
        }
    }
    
    logger.warning(f"Using fallback creative concept for {style}")
    return concepts.get(style, concepts["instagram_ad"])


def refine_creative_text(
    groq_client,
    original_headline: str,
    original_subheadline: str,
    original_cta: str,
    brand_name: str = "",
    product_type: str = "premium product"
) -> dict:
    """
    Optional: Refine user-provided text using Groq for better copy.
    Call this if user hasn't provided text or wants AI suggestions.
    """
    
    if not groq_client:
        return {
            "headline": original_headline or "Discover Premium Quality",
            "subheadline": original_subheadline or "Experience the difference",
            "cta": original_cta or "Shop Now"
        }
    
    try:
        prompt = f"""You are a copywriting expert specializing in advertising and marketing.

Improve these marketing texts for maximum impact. Keep them concise and compelling.

Brand: {brand_name or 'Premium Brand'}
Product: {product_type}

Current Headline: "{original_headline or '(suggest)'}"
Current Subheadline: "{original_subheadline or '(suggest)'}"
Current CTA: "{original_cta or '(suggest)'}"

Return JSON with improved versions:
{{
  "headline": "Better headline (max 6 words)",
  "subheadline": "Better subheadline (max 10 words)",
  "cta": "Better CTA (1-3 words)"
}}"""

        message = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=256,
            response_format={"type": "json_object"},
            timeout=8.0,
        )

        refined = json.loads(message.choices[0].message.content)
        return refined
        
    except Exception as e:
        logger.error(f"Text refinement failed: {e}")
        # Return fallback
        return {
            "headline": original_headline or "Premium Quality Awaits",
            "subheadline": original_subheadline or "Experience excellence",
            "cta": original_cta or "Shop Now"
        }
