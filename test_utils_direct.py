#!/usr/bin/env python3
"""Test utils function with the exact same logic but with debug prints"""

import os
import hashlib
from io import BytesIO
from datetime import datetime
import base64
import random
from typing import List, Optional


def _meal_image_key(meal_name: str, ingredients_text: str, macros_text: str = "", style_tag: str = "v6_photoreal_with_amounts") -> str:
    data = f"{meal_name}|{ingredients_text}|{macros_text}|{style_tag}".encode(
        "utf-8")
    return hashlib.sha1(data).hexdigest()[:16]


def _get_genai_api_key() -> Optional[str]:
    """Retrieve Gemini API key from environment variables in order of preference."""
    candidates = ["GOOGLE_API_KEY", "GEMINI_API_KEY",
                  "GOOGLE_GENAI_API_KEY", "GENAI_API_KEY"]
    for var in candidates:
        val = os.getenv(var)
        if val:
            if len(candidates) > 1:
                print(
                    f"Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using {var}.")
            return val
    return None


def debug_maybe_generate_meal_image(meal_name: str, ingredients_text: str, preparation_text: str, out_dir: str, macros_text: str = "") -> Optional[str]:
    """Debug version of maybe_generate_meal_image with verbose output"""

    print(f"\n=== DEBUG MAYBE_GENERATE_MEAL_IMAGE ===")
    print(f"meal_name: {meal_name}")
    print(f"out_dir: {out_dir}")

    # Check if enabled
    enabled = str(os.getenv("ENABLE_MEAL_IMAGES", "")
                  ).lower() in {"1", "true", "yes"}
    print(f"enabled: {enabled}")
    if not enabled:
        print("❌ RETURN None: Not enabled")
        return None

    # Skip image generation for vague or placeholder meal names
    excluded_names = ["—", "Flexible Choice within Guidelines",
                      "Generic Breakfast", "Generic Lunch", "Generic Snack", "Generic Dinner"]
    if meal_name in excluded_names or not meal_name.strip():
        print("❌ RETURN None: Excluded meal name")
        return None

    os.makedirs(out_dir, exist_ok=True)

    # Determine style
    name_low = meal_name.lower()
    ing_low = (ingredients_text or "").lower()
    is_smoothie_bowl = ("smoothie bowl" in name_low) or (
        "bowl" in name_low and ("smoothie" in name_low or "acai" in name_low))

    drink_name_tokens = ["smoothie", "shake", "juice", "latte", "mocktail",
                         "iced coffee", "iced tea", "ade", "lemonade", "milkshake", "tea", "coffee"]
    not_food_tokens = ["bowl", "curry", "soup", "stir-fry", "stir fry", "pasta",
                       "salad", "taco", "wrap", "rice", "noodle", "toast", "oat", "porridge", "pizza"]
    is_glass_drink = ((not is_smoothie_bowl) and any(
        tok in name_low for tok in drink_name_tokens) and not any(ft in name_low for ft in not_food_tokens))

    if is_glass_drink:
        style_tag = "v8_drink_glass_side"
    elif is_smoothie_bowl:
        style_tag = "v8_bowl_overhead"
    else:
        style_tag = "v8_food_overhead_plate"

    print(f"style_tag: {style_tag}")

    key = _meal_image_key(meal_name, ingredients_text,
                          macros_text=macros_text, style_tag=style_tag)
    dest_path = os.path.join(out_dir, f"{key}.jpg")
    rng = random.Random(int(key, 16))

    print(f"cache key: {key}")
    print(f"dest_path: {dest_path}")

    # Check cache
    if os.path.exists(dest_path):
        print(f"✅ RETURN cached: {dest_path}")
        return dest_path

    # Get API key
    api_key = _get_genai_api_key()
    if not api_key:
        print("❌ RETURN None: No API key")
        return None

    print(f"api_key: {api_key[:20]}...")

    # Generate image
    image_bytes = None
    candidate_images: List[bytes] = []
    num_variants = 3

    # Path A: new google-genai client
    print("\n🔄 Trying new google-genai client (Path A)...")
    try:
        from google import genai as new_genai
        from google.genai import types as new_genai_types
        client = new_genai.Client(api_key=api_key)
        print("✅ Client created")

        # Try likely image models
        for model_name in ["gemini-2.0-flash-preview-image-generation", "imagen-3.0-generate-001", "gemini-2.5-flash-image-preview"]:
            print(f"\n🤖 Trying model: {model_name}")
            try:
                if model_name in ["gemini-2.5-flash-image-preview", "gemini-2.0-flash-preview-image-generation"]:
                    print("📞 Calling generate_content with IMAGE+TEXT modalities...")

                    # Create prompt
                    angle_choice = "overhead"
                    header_line = f"Photorealistic overhead (top-down 90°) food photo of {meal_name}."
                    angle_line = "Camera angle: overhead (top-down 90°)."
                    vessel_line = "Serve on a ceramic plate or shallow bowl on a natural surface with believable cutlery; avoid perfect symmetry."
                    aspect_line = "Aspect: 3:2 or 4:3, natural composition; preserve aspect ratio."
                    realism_lines = [
                        "Natural daylight (window light), soft realistic shadows, true-to-life colors.",
                        "Shallow depth of field where appropriate (background softly out of focus).",
                        "Imperfect plating, a few realistic crumbs/smears; subtle steam/condensation when warm.",
                        "Light table clutter: linen napkin, fork/spoon; no excessive props.",
                        "No text, no labels, no borders, no watermarks, no hands, no logos."
                    ]

                    prompt_parts = [
                        header_line, angle_line, aspect_line,
                        "Ingredients and approximate amounts to depict:",
                        ingredients_text, vessel_line, *realism_lines,
                        "Food magazine quality, high dynamic range, crisp detail."
                    ]
                    prompt = "\n".join(prompt_parts)

                    resp = client.models.generate_content(
                        model=model_name,
                        contents=[prompt],
                        config=new_genai_types.GenerateContentConfig(
                            response_modalities=[
                                new_genai_types.Modality.IMAGE, new_genai_types.Modality.TEXT],
                            candidate_count=num_variants,
                        )
                    )
                    print("✅ API call successful")

                    if resp.candidates:
                        print(f"✅ Got {len(resp.candidates)} candidate(s)")
                        for cand in resp.candidates:
                            if cand.content and cand.content.parts:
                                for part in cand.content.parts:
                                    if hasattr(part, "inline_data") and hasattr(part.inline_data, "data") and part.inline_data.data:
                                        print("✅ Found image data in candidate!")
                                        candidate_images.append(
                                            part.inline_data.data)
                    else:
                        print("❌ No candidates returned")

                elif hasattr(client, "images") and hasattr(client.images, "generate"):
                    print("📞 Calling client.images.generate...")
                    for _ in range(num_variants):
                        resp = client.images.generate(
                            model=model_name, prompt=prompt)
                        if hasattr(resp, "images") and len(resp.images) > 0:
                            img = resp.images[0]
                            if hasattr(img, "image_bytes") and img.image_bytes:
                                candidate_images.append(img.image_bytes)
                            elif hasattr(img, "data") and img.data:
                                candidate_images.append(img.data)
                else:
                    print("❌ client.images.generate not available")

                if candidate_images:
                    print(
                        f"✅ Found {len(candidate_images)} candidate images, breaking")
                    break

            except Exception as e:
                print(f"❌ Error with {model_name}: {e}")
                continue

    except Exception as e:
        print(f"❌ Client error: {e}")

    # Select best candidate
    print(f"\n📊 candidate_images count: {len(candidate_images)}")
    print(
        f"📊 image_bytes before selection: {'Set' if image_bytes else 'None'}")

    if candidate_images and not image_bytes:
        image_bytes = candidate_images[0]
        print(f"✅ Selected first candidate: {len(image_bytes)} bytes")
    else:
        print(f"❌ No candidates to select from")

    # Check if we have image bytes
    if not image_bytes:
        print("❌ RETURN None: No image bytes")
        return None

    print(f"✅ Have image_bytes: {len(image_bytes)} bytes")

    # Process and save image
    print("\n🖼️ Processing image...")
    try:
        from PIL import Image as PILImage, ImageEnhance, ImageFilter, ImageChops

        # Decode if needed
        if isinstance(image_bytes, str):
            try:
                image_bytes = base64.b64decode(image_bytes)
                print("✅ Decoded base64 string")
            except Exception:
                print("⚠️ Failed to decode base64, using as-is")
                pass

        img = PILImage.open(BytesIO(image_bytes))
        print(f"✅ Loaded image: {img.size}, mode: {img.mode}")

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            print("✅ Converted to RGB")

        max_px = 1400
        img.thumbnail((max_px, max_px), PILImage.LANCZOS)
        print(f"✅ Resized to: {img.size}")

        # Save image
        img.save(dest_path, format="JPEG", quality=70,
                 optimize=True, progressive=True)
        print(f"✅ SAVED: {dest_path}")

        return dest_path

    except Exception as outer_e:
        print(f"❌ RETURN None: Error processing image: {outer_e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Set environment variables
    os.environ['ENABLE_MEAL_IMAGES'] = '1'
    os.environ['GOOGLE_API_KEY'] = 'AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4'

    # Test
    result = debug_maybe_generate_meal_image(
        meal_name="High-Protein Greek Yogurt Bowl",
        ingredients_text="- 200g Greek Yogurt (0% fat)\n- 30g Protein Granola\n- 100g Mixed Berries\n- 15g Chia Seeds\n- 10g Honey",
        preparation_text="Combine yogurt, granola, berries, chia seeds, and honey in a bowl. (2 mins)",
        out_dir="debug_direct_test"
    )

    if result:
        print(f"\n🎉 SUCCESS: {result}")
        if os.path.exists(result):
            size = os.path.getsize(result)
            print(f"📊 File size: {size:,} bytes")
    else:
        print("\n❌ FAILED: No image generated")
