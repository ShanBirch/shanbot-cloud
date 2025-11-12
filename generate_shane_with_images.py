#!/usr/bin/env python3
"""Generate Shane's Week 1 meal plan with images enabled"""

import os
from client_configs import ALL_CLIENT_DATA
from utils import calculate_targets_by_sex, calculate_age
from weekly_meal_plan_generator import create_pdf


def main():
    # Force enable images and set API key in environment
    os.environ["ENABLE_MEAL_IMAGES"] = "1"
    os.environ["GOOGLE_API_KEY"] = "AIzaSyCGawrpt6EFWeaGDQ3rgf2yMS8-DMcXw0Y"

    print("=== GENERATING SHANE'S MEAL PLAN WITH IMAGES ===")
    print(f"ENABLE_MEAL_IMAGES: {os.environ.get('ENABLE_MEAL_IMAGES')}")
    print(
        f"GOOGLE_API_KEY: {'Set' if os.environ.get('GOOGLE_API_KEY') else 'Not set'}")
    print()

    # Get Shane's data
    shane_data = ALL_CLIENT_DATA["Shane Minahan"]
    print(f"Client: {shane_data['name']}")
    print(f"Goal: {shane_data['goal_description']}")

    # Calculate targets
    age = calculate_age(shane_data["dob"])
    target_cal, target_protein, target_carbs, target_fats = calculate_targets_by_sex(
        shane_data["sex"],
        shane_data["weight_kg"],
        shane_data["height_cm"],
        age,
        shane_data["activity_factor"],
        500  # 500 cal deficit for fat loss
    )

    print(f"\nDaily Targets:")
    print(f"Calories: {target_cal}")
    print(f"Protein: {target_protein}g")
    print(f"Carbs: {target_carbs}g")
    print(f"Fats: {target_fats}g")
    print()

    # Generate Week 1 PDF with images
    print("Generating Week 1 meal plan PDF with photos...")
    try:
        create_pdf(shane_data, week=1)
        print("✅ Successfully generated Shane Week 1 meal plan PDF with images!")
        print("📁 Location: meal plans/Shane Minahan - Week 1.pdf")

        # Check if any images were actually created
        import glob
        image_files = glob.glob("meal plans/images/*.jpg")
        if image_files:
            print(f"✅ {len(image_files)} meal images generated")
            print("Sample images:")
            for img in image_files[:3]:
                print(f"  - {img}")
        else:
            print("⚠️ No images found in meal plans/images/")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
