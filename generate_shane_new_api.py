#!/usr/bin/env python3
"""Generate Shane's Week 1 meal plan with new API key"""

import os
from client_configs import ALL_CLIENT_DATA
from utils import calculate_targets_by_sex, calculate_age
from weekly_meal_plan_generator import create_pdf


def main():
    # Use the new API key you provided
    new_api_key = "GEMINI_API_KEY"  # Replace with the actual key from your curl command

    # Force enable images and set the new API key
    os.environ["ENABLE_MEAL_IMAGES"] = "1"
    os.environ["GOOGLE_API_KEY"] = new_api_key
    os.environ["GEMINI_API_KEY"] = new_api_key

    print("=== GENERATING SHANE'S MEAL PLAN WITH NEW API KEY ===")
    print(f"ENABLE_MEAL_IMAGES: {os.environ.get('ENABLE_MEAL_IMAGES')}")
    print(f"API Key: {new_api_key[:20]}..." if len(
        new_api_key) > 20 else f"API Key: {new_api_key}")
    print()

    # Test the API key first
    print("Testing API key...")
    try:
        import google.generativeai as genai
        genai.configure(api_key=new_api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content("Test")
        print("✅ API key working!")
    except Exception as e:
        print(f"❌ API key test failed: {e}")
        return

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

    # Generate Week 1 PDF with images
    print("Generating Week 1 meal plan PDF with photos...")
    try:
        create_pdf(shane_data, week=1)
        print("✅ Successfully generated Shane Week 1 meal plan PDF with images!")

        # Check for images
        import glob
        image_files = glob.glob("meal plans/images/*.jpg")
        print(f"✅ {len(image_files)} meal images generated")

        # Get file size to confirm it's different
        import os
        pdf_path = "meal plans/Shane Minahan - Week 1.pdf"
        if os.path.exists(pdf_path):
            size = os.path.getsize(pdf_path)
            print(f"📄 PDF size: {size:,} bytes")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
