#!/usr/bin/env python3
"""Debug image generation for meal plans"""

import os
from utils import _get_genai_api_key, maybe_generate_meal_image


def main():
    print("=== DEBUG IMAGE GENERATION ===")
    print(f"ENABLE_MEAL_IMAGES: {os.getenv('ENABLE_MEAL_IMAGES')}")

    api_key = _get_genai_api_key()
    print(f"API Key found: {'Yes' if api_key else 'No'}")
    if api_key:
        print(f"API Key prefix: {api_key[:10]}...")

    # Test image generation
    print("\nTesting image generation...")
    test_path = maybe_generate_meal_image(
        "Grilled Chicken Breast with Vegetables",
        "- 180g Chicken Breast\n- 150g Broccoli\n- 100g Sweet Potato",
        "Grill chicken, steam vegetables, roast sweet potato",
        "test_images"
    )
    print(
        f"Test result: {test_path if test_path else 'Failed - no image generated'}")

    if test_path and os.path.exists(test_path):
        print(f"✅ Image successfully created at: {test_path}")
        print(f"File size: {os.path.getsize(test_path)} bytes")
    else:
        print("❌ No image was generated")

        # Check environment variables that could affect this
        env_vars = [
            "GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_API_KEY", "GENAI_API_KEY"
        ]
        print("\nEnvironment variables:")
        for var in env_vars:
            val = os.getenv(var)
            if val:
                print(f"  {var}: {val[:10]}... (length: {len(val)})")
            else:
                print(f"  {var}: Not set")


if __name__ == "__main__":
    main()
