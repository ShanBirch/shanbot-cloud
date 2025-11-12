#!/usr/bin/env python3
"""Generate Shane's meal plan with working Gemini 2.5 Flash photos"""

import os
import shutil
from client_configs import ALL_CLIENT_DATA
from weekly_meal_plan_generator import create_pdf, calculate_targets_by_sex, calculate_age
from datetime import date


def main():
    # Set environment variables for image generation
    os.environ['ENABLE_MEAL_IMAGES'] = '1'
    os.environ['GOOGLE_API_KEY'] = 'AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4'

    print("=== GENERATING SHANE'S MEAL PLAN WITH GEMINI 2.5 FLASH PHOTOS ===")
    print(f"🔑 API Key: {os.getenv('GOOGLE_API_KEY')[:20]}...")
    print(f"🖼️ Images enabled: {os.getenv('ENABLE_MEAL_IMAGES')}")

    # Get Shane's data
    shane_data = ALL_CLIENT_DATA["Shane Minahan"]

    # Calculate nutrition targets
    age = calculate_age(shane_data["dob"])
    target_cal, target_protein, target_carbs, target_fats = calculate_targets_by_sex(
        shane_data["sex"],
        shane_data["weight_kg"],
        shane_data["height_cm"],
        age,
        shane_data["activity_factor"],
        500  # 500 calorie deficit for fat loss
    )

    print(f"\n👤 Client: {shane_data['name']}")
    print(f"🎯 Goal: {shane_data['goal_description']}")
    print(
        f"📊 Daily Targets: {target_cal} cal, {target_protein}g protein, {target_carbs}g carbs, {target_fats}g fats")

    # Clear old images for fresh generation
    images_dir = os.path.join("meal plans", "images")
    if os.path.exists(images_dir):
        shutil.rmtree(images_dir)
        print(f"🗑️ Cleared old images from: {images_dir}")
    os.makedirs(images_dir, exist_ok=True)

    print("\n🍽️ Generating Week 1 meal plan with Gemini 2.5 Flash photos...")
    print("⏳ This may take a few minutes as each meal photo is generated...")

    # Generate the PDF with images
    try:
        create_pdf(shane_data, week=1)

        # Check results
        pdf_path = os.path.join(
            "meal plans", f"{shane_data['name']} - Week 1.pdf")

        if os.path.exists(pdf_path):
            pdf_size = os.path.getsize(pdf_path)
            print(f"\n✅ SUCCESS! Meal plan PDF generated!")
            print(f"📄 Location: {pdf_path}")
            print(f"📊 PDF size: {pdf_size:,} bytes")

            # Check how many images were generated
            if os.path.exists(images_dir):
                generated_images = [f for f in os.listdir(
                    images_dir) if f.endswith('.jpg')]
                print(f"🖼️ {len(generated_images)} meal photos generated")

                if generated_images:
                    print("\n📷 Sample generated images:")
                    for i, img_name in enumerate(generated_images[:3]):
                        img_path = os.path.join(images_dir, img_name)
                        img_size = os.path.getsize(img_path)
                        print(f"   {i+1}. {img_name} ({img_size:,} bytes)")

                    if len(generated_images) > 3:
                        print(f"   ... and {len(generated_images) - 3} more")

                    print(f"\n🎨 All photos generated using Gemini 2.5 Flash")
                    print(
                        f"📈 Expected PDF size with photos: {pdf_size/1024/1024:.1f} MB")

                    # Check if PDF size indicates images are included
                    if pdf_size > 5_000_000:  # > 5MB suggests images are included
                        print("✅ PDF size suggests images are successfully embedded!")
                    else:
                        print(
                            "⚠️ PDF size seems small - images might not be embedded")

                else:
                    print("⚠️ No images found in images directory")

        else:
            print("❌ PDF was not created")

    except Exception as e:
        print(f"❌ Error generating meal plan: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
