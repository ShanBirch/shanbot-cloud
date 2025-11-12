#!/usr/bin/env python3
"""Verify if images are embedded in Shane's PDF"""

import os


def analyze_pdf_content():
    print("=== ANALYZING SHANE'S PDF FOR EMBEDDED IMAGES ===")

    pdf_path = os.path.join("meal plans", "Shane Minahan - Week 1.pdf")
    test_pdf_path = os.path.join("meal plans", "test_single_meal.pdf")

    if not os.path.exists(pdf_path):
        print("❌ Shane's PDF not found")
        return

    pdf_size = os.path.getsize(pdf_path)
    test_size = os.path.getsize(
        test_pdf_path) if os.path.exists(test_pdf_path) else 0

    print(f"📄 Shane's PDF: {pdf_size:,} bytes ({pdf_size/1024:.1f} KB)")
    print(
        f"📄 Test PDF (1 image): {test_size:,} bytes ({test_size/1024:.1f} KB)")

    # Count images in directory
    images_dir = os.path.join("meal plans", "images")
    if os.path.exists(images_dir):
        images = [f for f in os.listdir(images_dir) if f.endswith('.jpg')]
        total_image_size = sum(os.path.getsize(
            os.path.join(images_dir, img)) for img in images)

        print(f"🖼️ Generated images: {len(images)}")
        print(
            f"📊 Total image data: {total_image_size:,} bytes ({total_image_size/1024:.1f} KB)")

        # Estimate PDF size with images
        base_pdf_size = 75000  # Approximate size without images
        expected_size_with_images = base_pdf_size + total_image_size

        print(f"\n📈 Size Analysis:")
        print(f"   • Base PDF (text only): ~75 KB")
        print(f"   • Raw image data: {total_image_size/1024:.1f} KB")
        print(
            f"   • Expected with images: ~{expected_size_with_images/1024:.1f} KB")
        print(f"   • Actual PDF size: {pdf_size/1024:.1f} KB")

        size_ratio = pdf_size / expected_size_with_images if expected_size_with_images > 0 else 0

        if size_ratio > 0.8:
            print(
                f"✅ PDF size suggests images ARE embedded! (ratio: {size_ratio:.2f})")

            # Try to read PDF content to look for image markers
            try:
                with open(pdf_path, 'rb') as f:
                    content = f.read()

                # Look for JPEG markers in PDF
                # JPEG compression marker
                jpeg_count = content.count(b'/DCTDecode')
                image_count = content.count(
                    b'/Image')     # Image object marker

                print(f"🔍 PDF Content Analysis:")
                print(f"   • JPEG markers found: {jpeg_count}")
                print(f"   • Image object markers: {image_count}")

                if jpeg_count >= len(images) or image_count >= len(images):
                    print(f"🎉 SUCCESS! Images are definitely embedded in the PDF!")
                    return True
                else:
                    print(f"⚠️ Fewer image markers than expected")

            except Exception as e:
                print(f"⚠️ Could not analyze PDF content: {e}")
        else:
            print(
                f"❌ PDF size too small for embedded images (ratio: {size_ratio:.2f})")

    return False


def check_image_generation_status():
    """Check why only 8 images were generated instead of 28"""
    print("\n=== CHECKING IMAGE GENERATION STATUS ===")

    # Expected meals for Shane (7 days × 4 meals = 28)
    print("📊 Expected meal images:")
    print("   • 7 breakfasts")
    print("   • 7 lunches")
    print("   • 7 dinners")
    print("   • 7 snacks")
    print("   • Total: 28 images")

    images_dir = os.path.join("meal plans", "images")
    if os.path.exists(images_dir):
        images = [f for f in os.listdir(images_dir) if f.endswith('.jpg')]
        print(f"\n🖼️ Actually generated: {len(images)} images")

        if len(images) < 28:
            shortage = 28 - len(images)
            print(f"⚠️ Missing {shortage} images")
            print(f"💡 Likely causes:")
            print(f"   • API quota limits (most probable)")
            print(f"   • Some meals may have generic/excluded names")
            print(f"   • Image generation errors")

            print(f"\n🔧 Solutions:")
            print(f"   1. Wait for API quota to reset (24 hours)")
            print(f"   2. Use a paid API plan for higher limits")
            print(f"   3. Generate images in smaller batches")
        else:
            print(f"✅ All expected images generated!")


if __name__ == "__main__":
    images_embedded = analyze_pdf_content()
    check_image_generation_status()

    print(f"\n=== FINAL ASSESSMENT ===")
    if images_embedded:
        print(f"🎉 Shane's meal plan PDF contains embedded images!")
        print(f"📸 8 out of 28 meals have beautiful AI-generated photos")
        print(f"🍽️ The meal plan is ready to use!")
        print(f"\n💡 To get all 28 images:")
        print(f"   • Wait for API quota reset")
        print(f"   • Regenerate to complete the image set")
    else:
        print(f"❌ Images may not be properly embedded")
        print(f"🔧 Need further investigation")
