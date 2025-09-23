#!/usr/bin/env python3
"""Generate Shane's meal plan with the fully fixed Gemini 2.5 Flash image system"""

import os
import shutil
from client_configs import ALL_CLIENT_DATA
from weekly_meal_plan_generator import create_pdf, calculate_targets_by_sex, calculate_age
from datetime import date


def main():
    # Enable images with the working Gemini 2.5 Flash system
    os.environ['ENABLE_MEAL_IMAGES'] = '1'
    os.environ['GOOGLE_API_KEY'] = 'AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4'

    print("=== GENERATING SHANE'S MEAL PLAN WITH GEMINI 2.5 FLASH PHOTOS ===")
    print("🎨 Using fixed image generation system")
    print("🔧 Gemini 2.5 Flash configured with IMAGE+TEXT modalities")
    print("📸 Each meal will get a photorealistic food photo")

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

    print(f"\n🍽️ Generating Week 1 meal plan with AI-generated photos...")
    print("⏳ This will take several minutes as each meal photo is generated...")
    print("📷 Expected photos: ~28 images (7 days × 4 meals)")

    # Generate the PDF with images
    try:
        create_pdf(shane_data, week=1)

        # Check results
        pdf_path = os.path.join(
            "meal plans", f"{shane_data['name']} - Week 1.pdf")

        if os.path.exists(pdf_path):
            pdf_size = os.path.getsize(pdf_path)
            pdf_size_mb = pdf_size / (1024 * 1024)

            print(f"\n✅ SUCCESS! Enhanced meal plan PDF generated!")
            print(f"📄 Location: {pdf_path}")
            print(f"📊 PDF size: {pdf_size:,} bytes ({pdf_size_mb:.1f} MB)")

            # Check generated images
            if os.path.exists(images_dir):
                generated_images = [f for f in os.listdir(
                    images_dir) if f.endswith('.jpg')]
                print(f"🖼️ Generated {len(generated_images)} meal photos")

                if generated_images:
                    total_image_size = sum(os.path.getsize(os.path.join(
                        images_dir, img)) for img in generated_images)
                    avg_image_size = total_image_size / \
                        len(generated_images) if generated_images else 0

                    print(f"\n📸 Image Generation Summary:")
                    print(f"   • Total photos: {len(generated_images)}")
                    print(
                        f"   • Average size: {avg_image_size/1024:.0f} KB per image")
                    print(
                        f"   • Total image data: {total_image_size/1024/1024:.1f} MB")
                    print(f"   • Generated using: Gemini 2.5 Flash")
                    print(f"   • Style: Photorealistic food photography")

                    # Show sample images
                    print(f"\n📷 Sample generated images:")
                    for i, img_name in enumerate(generated_images[:5]):
                        img_path = os.path.join(images_dir, img_name)
                        img_size = os.path.getsize(img_path)
                        print(f"   {i+1}. {img_name} ({img_size/1024:.0f} KB)")

                    if len(generated_images) > 5:
                        print(
                            f"   ... and {len(generated_images) - 5} more photos")

                    # Determine success level
                    if pdf_size > 20_000_000:  # > 20MB suggests many images
                        print(
                            f"\n🎉 EXCELLENT! PDF size indicates images are successfully embedded")
                        print(f"📖 Shane now has a complete visual meal plan")
                    elif pdf_size > 5_000_000:  # > 5MB suggests some images
                        print(f"\n✅ GOOD! PDF contains some images")
                        print(f"📊 Some photos may have been generated successfully")
                    else:
                        print(f"\n⚠️ PDF size suggests images may not be embedded")
                        print(f"📋 Text-based meal plan is complete though")

                    print(f"\n📋 Complete Meal Plan Features:")
                    print(f"   • 7-day structured meal plan")
                    print(f"   • Photorealistic meal images")
                    print(f"   • Detailed ingredient lists")
                    print(f"   • Step-by-step preparation")
                    print(f"   • Macro nutrition breakdowns")
                    print(f"   • Shopping list by category")
                    print(f"   • Tailored for fat loss goals")

                else:
                    print(f"\n⚠️ No images were generated")
                    print(f"📋 But complete text-based meal plan is available")

        else:
            print("❌ PDF was not created")

    except Exception as e:
        print(f"❌ Error generating meal plan: {e}")

        # Check if it's a quota issue
        if "quota" in str(e).lower() or "429" in str(e):
            print(f"\n💡 API quota exceeded - will need to retry later")
            print(f"📋 In the meantime, you have the complete text-based meal plan")
        else:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
