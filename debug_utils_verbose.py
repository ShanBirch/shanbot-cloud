#!/usr/bin/env python3
"""Debug with verbose output to see what's happening inside utils.py"""

import os
from utils import _meal_image_key, _get_genai_api_key


def debug_step_by_step():
    print("=== STEP-BY-STEP DEBUG ===")

    # Set environment variables
    os.environ['ENABLE_MEAL_IMAGES'] = '1'
    os.environ['GOOGLE_API_KEY'] = 'AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4'

    # Test parameters
    meal_name = "High-Protein Greek Yogurt Bowl"
    ingredients_text = "- 200g Greek Yogurt (0% fat)\n- 30g Protein Granola\n- 100g Mixed Berries\n- 15g Chia Seeds\n- 10g Honey"
    preparation_text = "Combine yogurt, granola, berries, chia seeds, and honey in a bowl. (2 mins)"
    out_dir = "debug_step_by_step"
    macros_text = ""

    print(f"ENABLE_MEAL_IMAGES: {os.getenv('ENABLE_MEAL_IMAGES')}")

    # Check if enabled
    enabled = str(os.getenv("ENABLE_MEAL_IMAGES", "")
                  ).lower() in {"1", "true", "yes"}
    print(f"enabled check: {enabled}")

    if not enabled:
        print("❌ Not enabled, would return None")
        return

    # Check meal name
    print(f"meal_name: '{meal_name}'")
    excluded_names = ["—", "Flexible Choice within Guidelines",
                      "Generic Breakfast", "Generic Lunch", "Generic Snack", "Generic Dinner"]
    if meal_name in excluded_names or not meal_name.strip():
        print("❌ Excluded meal name, would return None")
        return

    print("✅ Meal name is valid")

    # Create output directory
    os.makedirs(out_dir, exist_ok=True)
    print(f"✅ Created output directory: {out_dir}")

    # Check style detection
    name_low = meal_name.lower()
    ing_low = (ingredients_text or "").lower()
    is_smoothie_bowl = ("smoothie bowl" in name_low) or (
        "bowl" in name_low and ("smoothie" in name_low or "acai" in name_low))
    print(f"is_smoothie_bowl: {is_smoothie_bowl}")

    drink_name_tokens = ["smoothie", "shake", "juice", "latte", "mocktail",
                         "iced coffee", "iced tea", "ade", "lemonade", "milkshake", "tea", "coffee"]
    not_food_tokens = ["bowl", "curry", "soup", "stir-fry", "stir fry", "pasta",
                       "salad", "taco", "wrap", "rice", "noodle", "toast", "oat", "porridge", "pizza"]
    is_glass_drink = ((not is_smoothie_bowl) and any(
        tok in name_low for tok in drink_name_tokens) and not any(ft in name_low for ft in not_food_tokens))
    print(f"is_glass_drink: {is_glass_drink}")

    if is_glass_drink:
        style_tag = "v8_drink_glass_side"
    elif is_smoothie_bowl:
        style_tag = "v8_bowl_overhead"
    else:
        style_tag = "v8_food_overhead_plate"

    print(f"style_tag: {style_tag}")

    # Check cache key
    key = _meal_image_key(meal_name, ingredients_text,
                          macros_text=macros_text, style_tag=style_tag)
    dest_path = os.path.join(out_dir, f"{key}.jpg")
    print(f"cache key: {key}")
    print(f"dest_path: {dest_path}")

    # Check if cached
    if os.path.exists(dest_path):
        print(f"✅ Cached image exists: {dest_path}")
        return dest_path
    else:
        print("❌ No cached image, need to generate")

    # Check API key
    api_key = _get_genai_api_key()
    print(f"API key: {api_key[:20] if api_key else 'None'}...")

    if not api_key:
        print("❌ No API key, would return None")
        return

    print("✅ API key available")

    # Test the actual API call logic
    print("\n🧪 Testing API call logic...")

    try:
        from google import genai as new_genai
        from google.genai import types as new_genai_types
        import random

        client = new_genai.Client(api_key=api_key)
        print("✅ Client created")

        # Generate the prompt (simplified version)
        rng = random.Random(int(key, 16))

        angle_choice = "overhead"  # Simplified for debugging
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
            header_line,
            angle_line,
            aspect_line,
            "Ingredients and approximate amounts to depict:",
            ingredients_text,
            vessel_line,
            *realism_lines,
            "Food magazine quality, high dynamic range, crisp detail."
        ]
        prompt = "\n".join(prompt_parts)

        print(f"Generated prompt: {prompt[:200]}...")

        # Try the working model
        model_name = "gemini-2.0-flash-preview-image-generation"
        print(f"\n📞 Calling {model_name}...")

        resp = client.models.generate_content(
            model=model_name,
            contents=[prompt],
            config=new_genai_types.GenerateContentConfig(
                response_modalities=[
                    new_genai_types.Modality.IMAGE,
                    new_genai_types.Modality.TEXT],
                candidate_count=1,
            )
        )

        print("✅ API call successful")

        if resp.candidates:
            print(f"✅ Got {len(resp.candidates)} candidate(s)")

            for cand in resp.candidates:
                if cand.content and cand.content.parts:
                    print(f"✅ Candidate has {len(cand.content.parts)} part(s)")

                    for part in cand.content.parts:
                        if hasattr(part, "inline_data") and hasattr(part.inline_data, "data") and part.inline_data.data:
                            print("✅ Found image data!")
                            print(
                                f"📊 Image data size: {len(part.inline_data.data)} bytes")

                            # Try to save the image using the same logic as utils.py
                            try:
                                import base64
                                from PIL import Image as PILImage
                                from io import BytesIO

                                # Decode the image
                                image_bytes = part.inline_data.data
                                if isinstance(image_bytes, str):
                                    image_bytes = base64.b64decode(image_bytes)

                                img = PILImage.open(BytesIO(image_bytes))
                                print(f"✅ Image loaded: {img.size}")

                                # Save to test location
                                test_path = os.path.join(
                                    out_dir, "test_image.jpg")
                                img.save(test_path, format="JPEG", quality=70,
                                         optimize=True, progressive=True)
                                print(f"✅ Saved test image: {test_path}")

                                return test_path

                            except Exception as save_error:
                                print(f"❌ Error saving image: {save_error}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print(f"❌ Part has no image data: {type(part)}")
                            if hasattr(part, "text"):
                                print(f"   Text: {part.text[:100]}...")
                else:
                    print("❌ Candidate has no content/parts")
        else:
            print("❌ No candidates in response")

    except Exception as e:
        print(f"❌ Error in API call: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    debug_step_by_step()
