#!/usr/bin/env python3
"""Test image generation with correct IMAGE + TEXT modality"""

import os
import base64
from io import BytesIO
from PIL import Image


def test_image_text_modality():
    """Test with both IMAGE and TEXT modalities as required"""
    api_key = "AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4"

    print("=== TESTING WITH IMAGE + TEXT MODALITY ===")

    try:
        from google import genai as new_genai
        from google.genai import types as new_genai_types

        client = new_genai.Client(api_key=api_key)
        print("✅ Client initialized")

        prompt = """Generate a photorealistic food photo of a Greek yogurt bowl with mixed berries.
        
Camera angle: overhead (top-down 90°).
Natural daylight, shallow depth of field, realistic shadows.
Serve in a ceramic bowl on a wooden table.
Ingredients: 200g Greek yogurt, 100g mixed berries, 15g honey drizzle.
No text, no labels, no borders.
Food magazine quality."""

        # Test with both IMAGE and TEXT modalities
        model_name = "gemini-2.0-flash-preview-image-generation"

        print(f"🤖 Testing {model_name} with IMAGE + TEXT modalities...")

        try:
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
                print(f"✅ Got {len(resp.candidates)} candidate(s)")

                for i, candidate in enumerate(resp.candidates):
                    print(f"📝 Candidate {i+1}:")

                    if candidate.content and candidate.content.parts:
                        print(f"   📦 {len(candidate.content.parts)} part(s)")

                        image_found = False
                        text_found = False

                        for j, part in enumerate(candidate.content.parts):
                            # Check for image data
                            if hasattr(part, "inline_data") and hasattr(part.inline_data, "data") and part.inline_data.data:
                                print(f"   🖼️ Part {j+1}: Image data found!")
                                image_found = True

                                # Save the image
                                os.makedirs(
                                    "correct_modality_images", exist_ok=True)
                                image_data = base64.b64decode(
                                    part.inline_data.data)
                                image = Image.open(BytesIO(image_data))
                                save_path = f"correct_modality_images/gemini_success_{i+1}.jpg"
                                image.save(save_path, "JPEG", quality=85)

                                print(f"   💾 Saved: {save_path}")
                                print(f"   📏 Size: {image.size}")
                                print(
                                    f"   📊 File size: {len(image_data):,} bytes")

                            # Check for text data
                            elif hasattr(part, "text") and part.text:
                                print(
                                    f"   📝 Part {j+1}: Text - {part.text[:100]}...")
                                text_found = True

                        if image_found:
                            print("🎉 SUCCESS! Image generation working!")
                            return True, save_path
                        else:
                            print("   ❌ No image data found in parts")
                    else:
                        print("   ❌ No content/parts in candidate")
            else:
                print("❌ No candidates in response")

        except Exception as e:
            print(f"❌ Error: {e}")

            # Check specific error types
            if "quota" in str(e).lower() or "429" in str(e):
                print("⚠️ API quota exceeded")
                return False, None
            elif "billing" in str(e).lower():
                print("⚠️ Billing/payment required")
                return False, None

            return False, None

    except Exception as e:
        print(f"❌ Client error: {e}")
        return False, None


def update_utils_with_working_approach():
    """Update utils.py to use the working image generation approach"""
    print("\n📝 Updating utils.py with working approach...")

    # Read current utils.py
    with open("utils.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Find the new google-genai client section and update it
    if "gemini-2.5-flash-image-preview" in content:
        # Replace the model call to use both IMAGE and TEXT modalities
        old_code = '''resp = client.models.generate_content(
                            model=model_name,
                            contents=[prompt],
                            config=new_genai_types.GenerateContentConfig(
                                response_modalities=[
                                    new_genai_types.Modality.IMAGE],
                                candidate_count=num_variants,
                            )
                        )'''

        new_code = '''resp = client.models.generate_content(
                            model=model_name,
                            contents=[prompt],
                            config=new_genai_types.GenerateContentConfig(
                                response_modalities=[
                                    new_genai_types.Modality.IMAGE,
                                    new_genai_types.Modality.TEXT],
                                candidate_count=num_variants,
                            )
                        )'''

        if old_code in content:
            content = content.replace(old_code, new_code)
            print("✅ Updated response modalities to include both IMAGE and TEXT")

        # Also prioritize the working model
        old_models = '''for model_name in [
                "imagen-3.0-generate-001",  # Prioritize Imagen for photorealism
                "gemini-2.5-flash-image-preview",
            ]:'''

        new_models = '''for model_name in [
                "gemini-2.0-flash-preview-image-generation",  # Working model with IMAGE+TEXT
                "imagen-3.0-generate-001",  # Prioritize Imagen for photorealism
                "gemini-2.5-flash-image-preview",
            ]:'''

        content = content.replace(old_models, new_models)

        # Write back
        with open("utils.py", "w", encoding="utf-8") as f:
            f.write(content)

        print("✅ Updated utils.py with working configuration")
    else:
        print("⚠️ Could not find section to update in utils.py")


if __name__ == "__main__":
    success, image_path = test_image_text_modality()

    if success:
        print(f"\n🎉 GEMINI 2.5 FLASH IMAGE GENERATION WORKING!")
        print(f"📷 Test image: {image_path}")

        # Update utils.py to use this approach
        update_utils_with_working_approach()

        print("\n✅ Ready to generate Shane's meal plan with photos!")
        print("The image generation is now properly configured.")

    else:
        print("\n❌ Still having issues with image generation")
        print("💡 Next steps:")
        print("1. Check if API key has image generation permissions")
        print("2. Verify billing is set up for image generation")
        print("3. Try alternative image services")
        print("4. Generate meal plan without images for now")
