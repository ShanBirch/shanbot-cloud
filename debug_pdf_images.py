#!/usr/bin/env python3
"""Debug PDF image embedding process"""

import os
from utils import maybe_generate_meal_image
from weekly_meal_plan_generator import parse_meal_fields, parse_meal_macros
from client_configs import ALL_CLIENT_DATA, ALL_CLIENT_MEAL_ROTATIONS
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image


def debug_image_embedding():
    print("=== DEBUGGING PDF IMAGE EMBEDDING ===")

    # Set environment variables
    os.environ['ENABLE_MEAL_IMAGES'] = '1'
    os.environ['GOOGLE_API_KEY'] = 'AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4'

    # Get Shane's data
    shane_data = ALL_CLIENT_DATA["Shane Minahan"]
    shane_meals = ALL_CLIENT_MEAL_ROTATIONS["Shane Minahan"]

    print(f"Client: {shane_data['name']}")
    print(f"Images enabled: {os.getenv('ENABLE_MEAL_IMAGES')}")

    # Test image generation for one specific meal
    print("\n🧪 Testing image generation for a specific meal...")

    # Get Day 1 breakfast
    breakfasts = shane_meals["breakfasts"]
    day1_breakfast = breakfasts[1]  # First breakfast rotation

    print(f"Test meal tuple: {day1_breakfast}")

    # Extract from tuple format (title, ingredients, preparation, macros)
    meal_name = day1_breakfast[0]
    ing_text = day1_breakfast[1]
    prep_text = day1_breakfast[2]
    macros_text = day1_breakfast[3]

    print(f"Parsed meal name: '{meal_name}'")
    print(f"Ingredients: {ing_text[:100]}...")
    print(f"Preparation: {prep_text[:100]}...")

    # Use the macros from the tuple
    macros_for_image = macros_text
    print(f"Macros: {macros_for_image}")

    # Test image generation
    img_path = maybe_generate_meal_image(
        meal_name,
        ing_text,
        prep_text,
        out_dir=os.path.join("meal plans", 'images'),
        macros_text=macros_for_image
    )

    if img_path:
        print(f"✅ Image generated: {img_path}")

        if os.path.exists(img_path):
            size = os.path.getsize(img_path)
            print(f"✅ Image file exists: {size:,} bytes")

            # Test ReportLab image processing
            try:
                print("\n🖼️ Testing ReportLab ImageReader...")
                reader = ImageReader(img_path)
                iw, ih = reader.getSize()
                print(f"✅ ImageReader successful: {iw}x{ih} pixels")

                # Test creating Image flowable
                from reportlab.lib.units import inch
                max_width = 3.5 * inch
                max_height = 4.5 * inch

                aspect = ih / float(iw) if iw else 0.75
                img_width = max_width
                img_height = img_width * aspect

                if img_height > max_height:
                    scale = max_height / img_height
                    img_width = img_width * scale
                    img_height = max_height

                print(
                    f"Calculated dimensions: {img_width:.1f} x {img_height:.1f}")

                image_flowable = Image(
                    img_path, width=img_width, height=img_height, hAlign='CENTER')
                print("✅ Image flowable created successfully")

                return True

            except Exception as e:
                print(f"❌ ReportLab processing error: {e}")
                import traceback
                traceback.print_exc()

        else:
            print(f"❌ Image file doesn't exist at: {img_path}")
    else:
        print("❌ No image path returned")

    return False


def test_existing_images():
    """Test the existing generated images"""
    print("\n=== TESTING EXISTING GENERATED IMAGES ===")

    images_dir = os.path.join("meal plans", "images")
    if os.path.exists(images_dir):
        images = [f for f in os.listdir(images_dir) if f.endswith('.jpg')]
        print(f"Found {len(images)} existing images")

        if images:
            # Test the first image
            test_img = os.path.join(images_dir, images[0])
            print(f"Testing: {test_img}")

            try:
                from reportlab.lib.utils import ImageReader
                from reportlab.platypus import Image
                from reportlab.lib.units import inch

                reader = ImageReader(test_img)
                iw, ih = reader.getSize()
                print(f"✅ Image readable: {iw}x{ih}")

                # Create flowable
                image_flowable = Image(test_img, width=3*inch, height=2*inch)
                print("✅ Image flowable created")

                return True

            except Exception as e:
                print(f"❌ Error processing existing image: {e}")
                return False
    else:
        print("❌ No images directory found")
        return False


if __name__ == "__main__":
    # Test new generation
    new_success = debug_image_embedding()

    # Test existing images
    existing_success = test_existing_images()

    print(f"\n=== SUMMARY ===")
    print(
        f"New image generation: {'✅ Working' if new_success else '❌ Issues'}")
    print(
        f"Existing image processing: {'✅ Working' if existing_success else '❌ Issues'}")

    if new_success and existing_success:
        print("🎉 Image system should be working in PDFs!")
    else:
        print("🔧 Need to investigate PDF embedding process")
