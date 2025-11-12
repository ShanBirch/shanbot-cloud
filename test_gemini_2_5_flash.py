#!/usr/bin/env python3
"""Test Gemini 2.5 Flash image generation specifically"""

import os
import google.generativeai as genai
from utils import maybe_generate_meal_image


def test_gemini_2_5_flash_direct():
    """Test Gemini 2.5 Flash image generation directly"""
    api_key = "AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4"

    print("=== TESTING GEMINI 2.5 FLASH IMAGE GENERATION ===")
    print(f"API Key: {api_key[:20]}...")

    # Configure Gemini
    genai.configure(api_key=api_key)

    # List available models to see what's actually available
    print("\n🔍 Checking available models...")
    try:
        models = genai.list_models()
        image_models = []
        for model in models:
            if 'image' in model.name.lower() or 'flash' in model.name.lower():
                image_models.append(model.name)
                print(f"  📷 {model.name}")

        if not image_models:
            print("❌ No image-capable models found")
            return False

    except Exception as e:
        print(f"❌ Error listing models: {e}")
        return False

    # Test specific models for image generation
    test_models = [
        "gemini-2.5-flash-exp",
        "gemini-2.5-flash",
        "gemini-2.0-flash-experimental",
        "models/gemini-2.5-flash-exp",
        "models/gemini-2.5-flash",
    ]

    # Also include any image models we found
    test_models.extend(image_models)

    prompt = """Generate a photorealistic image of a Greek yogurt bowl with mixed berries. 
    
Natural daylight, shallow depth of field, served in a ceramic bowl on a wooden table. 
Include 200g Greek yogurt, 100g mixed berries (blueberries, strawberries), 15g honey drizzle.
No text, no labels, food photography style."""

    print(f"\n🧪 Testing {len(test_models)} models for image generation...")

    for model_name in test_models:
        try:
            print(f"\n🤖 Testing: {model_name}")
            model = genai.GenerativeModel(model_name)

            # Try generating content with image request
            response = model.generate_content(prompt)

            if response and hasattr(response, 'candidates') and response.candidates:
                for i, candidate in enumerate(response.candidates):
                    if candidate.content and candidate.content.parts:
                        for j, part in enumerate(candidate.content.parts):
                            if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
                                print(
                                    f"✅ SUCCESS! Model {model_name} generated image data")
                                print(
                                    f"   📊 Image data size: {len(part.inline_data.data)} bytes")

                                # Save the image to test
                                import base64
                                from PIL import Image
                                from io import BytesIO

                                os.makedirs("test_flash_images", exist_ok=True)

                                # Decode and save image
                                image_data = base64.b64decode(
                                    part.inline_data.data)
                                image = Image.open(BytesIO(image_data))
                                test_path = f"test_flash_images/gemini_2_5_flash_test.jpg"
                                image.save(test_path, "JPEG", quality=85)

                                print(f"   💾 Saved test image: {test_path}")
                                print(f"   📏 Image size: {image.size}")
                                return True
                            else:
                                print(f"   ❌ No image data in part {j}")
                    else:
                        print(f"   ❌ No content/parts in candidate {i}")
            else:
                if response and hasattr(response, 'text') and response.text:
                    print(
                        f"   ℹ️ Got text response instead: {response.text[:100]}...")
                else:
                    print(f"   ❌ No candidates in response")

        except Exception as e:
            print(f"   ❌ Error with {model_name}: {e}")
            continue

    print("\n❌ No working image generation models found")
    return False


def test_with_utils_function():
    """Test using our existing utils function with environment variables set"""
    print("\n=== TESTING WITH UTILS FUNCTION ===")

    # Set environment variables
    os.environ["ENABLE_MEAL_IMAGES"] = "1"
    os.environ["GOOGLE_API_KEY"] = "AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4"

    # Clear test directory
    import shutil
    if os.path.exists("test_utils_images"):
        shutil.rmtree("test_utils_images")

    # Test image generation
    result = maybe_generate_meal_image(
        meal_name="Greek Yogurt Bowl",
        ingredients_text="- 200g Greek Yogurt\n- 100g Mixed Berries\n- 15g Honey",
        preparation_text="Mix yogurt with berries, drizzle honey",
        out_dir="test_utils_images"
    )

    if result:
        print(f"✅ Utils function success: {result}")
        if os.path.exists(result):
            size = os.path.getsize(result)
            print(f"📊 File size: {size:,} bytes")
        return True
    else:
        print("❌ Utils function returned None")
        return False


if __name__ == "__main__":
    # Test direct model access first
    direct_success = test_gemini_2_5_flash_direct()

    # Then test our utils function
    utils_success = test_with_utils_function()

    print("\n=== SUMMARY ===")
    print(
        f"Direct model test: {'✅ SUCCESS' if direct_success else '❌ FAILED'}")
    print(
        f"Utils function test: {'✅ SUCCESS' if utils_success else '❌ FAILED'}")

    if direct_success or utils_success:
        print("🎉 Gemini 2.5 Flash image generation is working!")
        print("Ready to generate Shane's meal plan with photos!")
    else:
        print("❌ Image generation still not working")
        print("Need to investigate further or try alternative services")
