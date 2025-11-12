#!/usr/bin/env python3
"""Debug the utils.py image generation function"""

import os
from utils import maybe_generate_meal_image, _get_genai_api_key


def debug_image_generation():
    print("=== DEBUGGING UTILS.PY IMAGE GENERATION ===")

    # Set environment variables
    os.environ['ENABLE_MEAL_IMAGES'] = '1'
    os.environ['GOOGLE_API_KEY'] = 'AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4'

    print(f"ENABLE_MEAL_IMAGES: {os.getenv('ENABLE_MEAL_IMAGES')}")
    print(f"GOOGLE_API_KEY: {os.getenv('GOOGLE_API_KEY')[:20]}...")

    # Test the API key retrieval function
    api_key = _get_genai_api_key()
    print(
        f"_get_genai_api_key() result: {api_key[:20] if api_key else 'None'}...")

    # Test a simple meal image generation
    print("\n🧪 Testing meal image generation...")

    meal_name = "High-Protein Greek Yogurt Bowl"
    ingredients = "- 200g Greek Yogurt (0% fat)\n- 30g Protein Granola\n- 100g Mixed Berries\n- 15g Chia Seeds\n- 10g Honey"
    preparation = "Combine yogurt, granola, berries, chia seeds, and honey in a bowl. (2 mins)"
    out_dir = "debug_meal_images"

    # Clear output directory
    import shutil
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    print(f"Meal: {meal_name}")
    print(f"Output dir: {out_dir}")

    try:
        result = maybe_generate_meal_image(
            meal_name=meal_name,
            ingredients_text=ingredients,
            preparation_text=preparation,
            out_dir=out_dir
        )

        if result:
            print(f"✅ SUCCESS: {result}")
            if os.path.exists(result):
                size = os.path.getsize(result)
                print(f"📊 File size: {size:,} bytes")
            else:
                print("❌ File path returned but file doesn't exist")
        else:
            print("❌ Function returned None")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def test_direct_api_call():
    """Test calling the API directly like utils.py does"""
    print("\n=== TESTING DIRECT API CALL ===")

    api_key = "AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4"

    try:
        from google import genai as new_genai
        from google.genai import types as new_genai_types

        client = new_genai.Client(api_key=api_key)

        prompt = """Photorealistic overhead food photo of High-Protein Greek Yogurt Bowl.
Camera angle: overhead (top-down 90°).
Aspect: 3:2 or 4:3, natural composition; preserve aspect ratio.
Ingredients: 200g Greek Yogurt, 30g Protein Granola, 100g Mixed Berries, 15g Chia Seeds, 10g Honey
Serve on a ceramic plate or shallow bowl on a natural surface with believable cutlery; avoid perfect symmetry.
Natural daylight (window light), soft realistic shadows, true-to-life colors.
Shallow depth of field where appropriate (background softly out of focus).
Imperfect plating, a few realistic crumbs/smears; subtle steam/condensation when warm.
Light table clutter: linen napkin, fork/spoon; no excessive props.
No text, no labels, no borders, no watermarks, no hands, no logos.
Food magazine quality, high dynamic range, crisp detail."""

        print("📞 Calling API...")

        resp = client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=[prompt],
            config=new_genai_types.GenerateContentConfig(
                response_modalities=[
                    new_genai_types.Modality.IMAGE,
                    new_genai_types.Modality.TEXT
                ],
                candidate_count=1,
            )
        )

        if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
            for part in resp.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                    print("✅ API returned image data!")
                    print(f"📊 Data size: {len(part.inline_data.data)} bytes")
                    return True

        print("❌ No image data in API response")
        return False

    except Exception as e:
        print(f"❌ API call failed: {e}")
        return False


if __name__ == "__main__":
    debug_image_generation()
    test_direct_api_call()
