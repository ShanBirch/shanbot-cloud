#!/usr/bin/env python3
"""Test the specific image generation models we found"""

import os
import base64
from io import BytesIO
from PIL import Image
import google.generativeai as genai


def test_image_generation_models():
    """Test the specific models that support image generation"""
    api_key = "AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4"

    print("=== TESTING SPECIFIC IMAGE GENERATION MODELS ===")

    # Configure Gemini
    genai.configure(api_key=api_key)

    # Models that specifically support image generation
    image_models = [
        "models/gemini-2.5-flash-image-preview",
        "models/gemini-2.0-flash-preview-image-generation",
        "models/imagen-3.0-generate-002",
        "models/imagen-4.0-generate-001",
        "models/imagen-4.0-fast-generate-001"
    ]

    prompt = """Photorealistic food photo of a Greek yogurt bowl with mixed berries.
    
Camera angle: overhead (top-down 90°).
Natural daylight, shallow depth of field, realistic shadows.
Serve in a ceramic bowl on a wooden table.
Ingredients: 200g Greek yogurt, 100g mixed berries (blueberries, strawberries), 15g honey drizzle.
No text, no labels, no borders.
Food magazine quality."""

    os.makedirs("working_images", exist_ok=True)

    for model_name in image_models:
        try:
            print(f"\n🤖 Testing: {model_name}")
            model = genai.GenerativeModel(model_name)

            # For image generation models, we need to specify we want image output
            if "image-generation" in model_name or "imagen" in model_name:
                # These models are designed specifically for image generation
                response = model.generate_content(prompt)
            else:
                # For gemini models with image capability, try both approaches
                try:
                    response = model.generate_content(prompt)
                except Exception as e:
                    print(f"   ⚠️ Standard approach failed: {e}")
                    # Try with explicit image request
                    continue

            if response and hasattr(response, 'candidates') and response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
                                print(
                                    f"   ✅ SUCCESS! Generated image with {model_name}")

                                # Save the image
                                image_data = base64.b64decode(
                                    part.inline_data.data)
                                image = Image.open(BytesIO(image_data))

                                # Clean model name for filename
                                clean_name = model_name.replace(
                                    "models/", "").replace("-", "_")
                                save_path = f"working_images/{clean_name}_test.jpg"
                                image.save(save_path, "JPEG", quality=85)

                                print(f"   💾 Saved: {save_path}")
                                print(f"   📏 Size: {image.size}")
                                print(
                                    f"   📊 File size: {len(image_data):,} bytes")

                                return model_name, save_path  # Return the working model
            else:
                print(f"   ❌ No image data returned")

        except Exception as e:
            print(f"   ❌ Error: {e}")

    return None, None


def update_utils_for_working_model(working_model):
    """Update utils.py to use the working model we found"""
    if not working_model:
        print("❌ No working model found to update utils.py")
        return

    print(f"\n📝 Updating utils.py to prioritize {working_model}...")

    # Read current utils.py
    with open("utils.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Find the model list and update it to prioritize our working model
    if "imagen-3.0-generate-001" in content:
        # Replace the model priority list
        old_models = '''for model_name in [
                "imagen-3.0-generate-001",  # Prioritize Imagen for photorealism
                "gemini-2.5-flash-image-preview",
            ]:'''

        new_models = f'''for model_name in [
                "{working_model}",  # Working model found through testing
                "imagen-3.0-generate-001",
                "gemini-2.5-flash-image-preview",
            ]:'''

        content = content.replace(old_models, new_models)

        # Write back
        with open("utils.py", "w", encoding="utf-8") as f:
            f.write(content)

        print(f"✅ Updated utils.py to prioritize {working_model}")
    else:
        print("⚠️ Could not find model list in utils.py to update")


if __name__ == "__main__":
    working_model, image_path = test_image_generation_models()

    if working_model:
        print(f"\n🎉 FOUND WORKING MODEL: {working_model}")
        print(f"📷 Test image: {image_path}")

        # Update utils.py to use this model
        update_utils_for_working_model(working_model)

        print("\n✅ Ready to generate Shane's meal plan with images!")
        print("Run the meal plan generator now...")

    else:
        print("\n❌ No working image generation models found")
        print("May need to check API permissions or try alternative services")
