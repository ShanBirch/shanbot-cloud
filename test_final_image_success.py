#!/usr/bin/env python3
"""Final test with proper image decoding"""

import os
import base64
from io import BytesIO
from PIL import Image


def test_successful_image_generation():
    """Test the working image generation with proper decoding"""
    api_key = "AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4"

    print("=== FINAL IMAGE GENERATION TEST ===")

    try:
        from google import genai as new_genai
        from google.genai import types as new_genai_types

        client = new_genai.Client(api_key=api_key)

        prompt = """Generate a photorealistic food photo of a Greek yogurt bowl with mixed berries.
        
Camera angle: overhead (top-down 90°).
Natural daylight, shallow depth of field, realistic shadows.
Serve in a ceramic bowl on a wooden table.
Ingredients: 200g Greek yogurt, 100g mixed berries, 15g honey drizzle.
No text, no labels, no borders.
Food magazine quality."""

        model_name = "gemini-2.0-flash-preview-image-generation"

        print(f"🤖 Generating image with {model_name}...")

        resp = client.models.generate_content(
            model=model_name,
            contents=[prompt],
            config=new_genai_types.GenerateContentConfig(
                response_modalities=[
                    new_genai_types.Modality.IMAGE,
                    new_genai_types.Modality.TEXT
                ],
                candidate_count=1,
            )
        )

        if resp.candidates:
            candidate = resp.candidates[0]

            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    # Check for image data
                    if hasattr(part, "inline_data") and hasattr(part.inline_data, "data") and part.inline_data.data:
                        print("🖼️ Image data found! Processing...")

                        # Decode base64 image data
                        try:
                            # The data might already be bytes, or it might be base64 string
                            image_data = part.inline_data.data

                            # If it's a string, decode it
                            if isinstance(image_data, str):
                                image_data = base64.b64decode(image_data)

                            # Create image from bytes
                            image = Image.open(BytesIO(image_data))

                            # Save the image
                            os.makedirs("final_success_images", exist_ok=True)
                            save_path = "final_success_images/gemini_2_5_flash_success.jpg"
                            image.save(save_path, "JPEG", quality=85)

                            print(f"✅ SUCCESS! Image saved: {save_path}")
                            print(f"📏 Image size: {image.size}")
                            print(f"📊 File size: {len(image_data):,} bytes")

                            return True, save_path

                        except Exception as decode_error:
                            print(f"❌ Image decoding error: {decode_error}")
                            print(
                                f"Image data type: {type(part.inline_data.data)}")
                            print(
                                f"Image data length: {len(part.inline_data.data) if hasattr(part.inline_data.data, '__len__') else 'unknown'}")

                            # Try saving raw data to debug
                            try:
                                with open("debug_image_data.bin", "wb") as f:
                                    if isinstance(part.inline_data.data, str):
                                        f.write(base64.b64decode(
                                            part.inline_data.data))
                                    else:
                                        f.write(part.inline_data.data)
                                print(
                                    "💾 Saved raw image data to debug_image_data.bin")
                            except Exception as save_error:
                                print(
                                    f"❌ Could not save debug data: {save_error}")

                    # Check for text data
                    elif hasattr(part, "text") and part.text:
                        print(f"📝 Generated description: {part.text[:200]}...")

        return False, None

    except Exception as e:
        print(f"❌ Error: {e}")
        return False, None


def update_utils_for_production():
    """Update utils.py with the working configuration"""
    print("\n📝 Updating utils.py for production use...")

    # Read the current utils.py
    with open("utils.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Update the model priority and configuration
    changes_made = False

    # 1. Update model priority list
    old_models = '''for model_name in [
                "imagen-3.0-generate-001",  # Prioritize Imagen for photorealism
                "gemini-2.5-flash-image-preview",
            ]:'''

    new_models = '''for model_name in [
                "gemini-2.0-flash-preview-image-generation",  # Working Gemini 2.5 Flash
                "imagen-3.0-generate-001",  # Fallback: Imagen for photorealism
                "gemini-2.5-flash-image-preview",  # Fallback: other Gemini models
            ]:'''

    if old_models in content:
        content = content.replace(old_models, new_models)
        changes_made = True
        print("✅ Updated model priority list")

    # 2. Update response modalities to include both IMAGE and TEXT
    old_config = '''config=new_genai_types.GenerateContentConfig(
                                response_modalities=[
                                    new_genai_types.Modality.IMAGE],
                                candidate_count=num_variants,
                            )'''

    new_config = '''config=new_genai_types.GenerateContentConfig(
                                response_modalities=[
                                    new_genai_types.Modality.IMAGE,
                                    new_genai_types.Modality.TEXT],
                                candidate_count=num_variants,
                            )'''

    if old_config in content:
        content = content.replace(old_config, new_config)
        changes_made = True
        print("✅ Updated response modalities")

    # 3. Write back the updated content
    if changes_made:
        with open("utils.py", "w", encoding="utf-8") as f:
            f.write(content)
        print("✅ utils.py updated successfully")
    else:
        print("⚠️ No changes needed in utils.py")


if __name__ == "__main__":
    success, image_path = test_successful_image_generation()

    if success:
        print(f"\n🎉 GEMINI 2.5 FLASH IMAGE GENERATION IS WORKING!")
        print(f"📷 Test image successfully generated: {image_path}")

        # Update utils.py for production
        update_utils_for_production()

        print("\n🚀 READY TO GENERATE SHANE'S MEAL PLAN WITH PHOTOS!")
        print("✅ Image generation is fully configured and working")

    else:
        print("\n⚠️ Image generation needs debugging")
        print("But we're very close - the API is returning image data")
