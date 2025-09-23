#!/usr/bin/env python3
"""Test image generation with the new API key"""

import os
from utils import maybe_generate_meal_image


def main():
    # Set your new API key
    new_api_key = "AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4"

    os.environ["ENABLE_MEAL_IMAGES"] = "1"
    os.environ["GOOGLE_API_KEY"] = new_api_key

    print("=== TESTING IMAGE GENERATION ===")
    print(f"API Key: {new_api_key[:20]}...")
    print()

    # Test direct image generation
    print("Testing image generation for a simple meal...")

    meal_name = "Grilled Chicken Breast with Vegetables"
    ingredients = "- 180g Chicken Breast (grilled)\n- 150g Broccoli (steamed)\n- 100g Sweet Potato (roasted)"
    preparation = "Grill chicken breast until golden. Steam broccoli. Roast sweet potato cubes."

    print(f"Meal: {meal_name}")
    print(f"Ingredients: {ingredients}")
    print()

    try:
        image_path = maybe_generate_meal_image(
            meal_name,
            ingredients,
            preparation,
            "test_images"
        )

        if image_path:
            print(f"✅ Image generated successfully: {image_path}")
            if os.path.exists(image_path):
                size = os.path.getsize(image_path)
                print(f"✅ Image file exists: {size:,} bytes")
            else:
                print("❌ Image path returned but file doesn't exist")
        else:
            print("❌ No image generated - function returned None")

    except Exception as e:
        print(f"❌ Error during image generation: {e}")
        import traceback
        traceback.print_exc()

    # Test different models/approaches
    print("\nTesting with different image models...")

    # Test with google-generativeai directly
    try:
        import google.generativeai as genai
        genai.configure(api_key=new_api_key)

        # Try different models
        for model_name in ["gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                print(f"Testing {model_name}...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    "Generate a simple test image of food")
                print(f"✅ {model_name} text generation works")
            except Exception as e:
                print(f"❌ {model_name} failed: {e}")

    except Exception as e:
        print(f"❌ Google GenerativeAI import/config failed: {e}")


if __name__ == "__main__":
    main()
