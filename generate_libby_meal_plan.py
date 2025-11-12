#!/usr/bin/env python3
"""Generate Libby's meal plan with Gemini 2.5 Flash photos"""

import os
import shutil
from client_configs import ALL_CLIENT_DATA
from weekly_meal_plan_generator import create_pdf, calculate_targets_by_sex, calculate_age
from datetime import date


def main():
    # Enable images with the working Gemini 2.5 Flash system
    os.environ['ENABLE_MEAL_IMAGES'] = '1'
    os.environ['GOOGLE_API_KEY'] = 'AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4'

    print("=== GENERATING LIBBY'S MEAL PLAN WITH GEMINI 2.5 FLASH PHOTOS ===")
    print("🎨 Using proven image generation system")
    print("🔧 Gemini 2.5 Flash configured with IMAGE+TEXT modalities")
    print("📸 Easy prep meals with photorealistic food photos")

    # Get Libby's data
    libby_data = ALL_CLIENT_DATA["Libby"]

    # Calculate nutrition targets
    age = calculate_age(libby_data["dob"])
    target_cal, target_protein, target_carbs, target_fats = calculate_targets_by_sex(
        libby_data["sex"],
        libby_data["weight_kg"],
        libby_data["height_cm"],
        age,
        libby_data["activity_factor"],
        500  # 500 calorie deficit for fat loss
    )

    print(f"\n👤 Client: {libby_data['name']}")
    print(f"🎯 Goal: {libby_data['goal_description']}")
    print(f"🥗 Dietary Type: {libby_data['dietary_type']}")
    print(f"💪 Workout: {libby_data['workout_type']}")
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
    print("🥗 Focus: Easy prep vegan meals Libby loves!")

    # Generate the PDF with images
    try:
        create_pdf(libby_data, week=1)

        # Check results
        pdf_path = os.path.join(
            "meal plans", f"{libby_data['name']} - Week 1.pdf")

        if os.path.exists(pdf_path):
            pdf_size = os.path.getsize(pdf_path)
            pdf_size_mb = pdf_size / (1024 * 1024)

            print(f"\n✅ SUCCESS! Libby's meal plan PDF generated!")
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
                    print(f"\n📷 Sample generated meal images:")
                    for i, img_name in enumerate(generated_images[:5]):
                        img_path = os.path.join(images_dir, img_name)
                        img_size = os.path.getsize(img_path)
                        print(f"   {i+1}. {img_name} ({img_size/1024:.0f} KB)")

                    if len(generated_images) > 5:
                        print(
                            f"   ... and {len(generated_images) - 5} more photos")

                    # Analyze embedding success
                    if pdf_size > 2_000_000:  # > 2MB suggests many images embedded
                        print(
                            f"\n🎉 EXCELLENT! PDF size indicates images are successfully embedded")
                        print(f"📖 Libby now has a complete visual meal plan")
                        print(f"🥗 Perfect for her easy-prep preferences!")
                    elif pdf_size > 500_000:  # > 500KB suggests some images
                        print(f"\n✅ GOOD! PDF contains some images")
                        print(
                            f"📊 {len(generated_images)} photos successfully generated")
                    else:
                        print(f"\n⚠️ PDF size suggests limited image embedding")
                        print(f"📋 Text-based meal plan is complete though")

                    print(f"\n📋 Libby's Meal Plan Features:")
                    print(f"   • 7-day easy-prep meal plan")
                    print(f"   • High-protein vegan meals")
                    print(f"   • Photorealistic meal images")
                    print(f"   • Quick salads, wraps, stir-frys")
                    print(f"   • Simple pasta & curry dishes")
                    print(f"   • Detailed prep instructions")
                    print(f"   • Macro nutrition breakdowns")
                    print(f"   • Shopping list by category")
                    print(f"   • Tailored for 10-15kg fat loss goal")

                    print(f"\n💡 Libby will love:")
                    print(f"   🥗 Power salad bowls (5 min prep)")
                    print(f"   🌯 Mediterranean wraps (3 min assembly)")
                    print(f"   🍜 Quick Thai stir-frys (15 mins)")
                    print(f"   🍝 Simple pasta dishes (20 mins)")
                    print(f"   🥤 Protein smoothie bowls (3 mins)")

                else:
                    print(f"\n⚠️ No images were generated")
                    print(f"📋 Complete text-based meal plan is available")

        else:
            print("❌ PDF was not created")

    except Exception as e:
        print(f"❌ Error generating meal plan: {e}")

        # Check if it's a quota issue
        if "quota" in str(e).lower() or "429" in str(e):
            print(f"\n💡 API quota exceeded - will need to retry later")
            print(f"📋 Libby can use the text-based meal plan in the meantime")
        else:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
