#!/usr/bin/env python3
"""Generate Shane's Week 1 meal plan with new API key and proper image embedding"""

import os
from client_configs import ALL_CLIENT_DATA
from utils import calculate_targets_by_sex, calculate_age
from weekly_meal_plan_generator import create_pdf


def main():
    # Use your new API key
    new_api_key = "AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4"

    # Force enable images and set the new API key
    os.environ["ENABLE_MEAL_IMAGES"] = "1"
    os.environ["GOOGLE_API_KEY"] = new_api_key
    os.environ["GEMINI_API_KEY"] = new_api_key

    print("=== GENERATING SHANE'S MEAL PLAN WITH NEW API KEY ===")
    print(f"ENABLE_MEAL_IMAGES: {os.environ.get('ENABLE_MEAL_IMAGES')}")
    print(f"API Key: {new_api_key[:20]}...")
    print()

    # Test the API key first
    print("Testing new API key...")
    try:
        import google.generativeai as genai
        genai.configure(api_key=new_api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content("Hello, respond with 'API working'")
        print(f"✅ API test successful: {response.text.strip()}")
    except Exception as e:
        print(f"❌ API key test failed: {e}")
        return

    # Clear any existing images to start fresh
    import glob
    import shutil
    if os.path.exists("meal plans/images"):
        print("Clearing old images...")
        shutil.rmtree("meal plans/images")

    # Get Shane's data
    shane_data = ALL_CLIENT_DATA["Shane Minahan"]
    print(f"Client: {shane_data['name']}")

    # Calculate targets
    age = calculate_age(shane_data["dob"])
    target_cal, target_protein, target_carbs, target_fats = calculate_targets_by_sex(
        shane_data["sex"],
        shane_data["weight_kg"],
        shane_data["height_cm"],
        age,
        shane_data["activity_factor"],
        500
    )

    print(f"Daily Targets: {target_cal} cal, {target_protein}g protein")
    print()

    # Generate Week 1 PDF with fresh images
    print("Generating Week 1 meal plan PDF with fresh photos...")
    try:
        create_pdf(shane_data, week=1)
        print("✅ Successfully generated Shane Week 1 meal plan PDF!")

        # Check results
        pdf_path = "meal plans/Shane Minahan - Week 1.pdf"
        if os.path.exists(pdf_path):
            size = os.path.getsize(pdf_path)
            print(f"📄 PDF size: {size:,} bytes")

        # Check for new images
        image_files = glob.glob("meal plans/images/*.jpg")
        print(f"🖼️ {len(image_files)} fresh meal images generated")

        if image_files:
            # Show sample image info
            sample_img = image_files[0]
            img_size = os.path.getsize(sample_img)
            print(f"Sample image: {sample_img} ({img_size:,} bytes)")

        # Confirm images are in PDF
        if size > 100000:  # If PDF is larger than 100KB, likely has images
            print("✅ PDF appears to contain images (large file size)")
        else:
            print("⚠️ PDF might not contain images (small file size)")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
