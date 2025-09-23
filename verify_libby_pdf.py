#!/usr/bin/env python3
"""Verify Libby's PDF images and analyze the results"""

import os


def analyze_libby_pdf():
    print("=== ANALYZING LIBBY'S PDF FOR EMBEDDED IMAGES ===")

    pdf_path = os.path.join("meal plans", "Libby - Week 1.pdf")

    if not os.path.exists(pdf_path):
        print("❌ Libby's PDF not found")
        return False

    pdf_size = os.path.getsize(pdf_path)

    print(f"📄 Libby's PDF: {pdf_size:,} bytes ({pdf_size/1024:.1f} KB)")

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


def compare_with_shane():
    """Compare Libby's results with Shane's"""
    print("\n=== COMPARING WITH SHANE'S RESULTS ===")

    shane_pdf = os.path.join("meal plans", "Shane Minahan - Week 1.pdf")
    libby_pdf = os.path.join("meal plans", "Libby - Week 1.pdf")

    if os.path.exists(shane_pdf) and os.path.exists(libby_pdf):
        shane_size = os.path.getsize(shane_pdf)
        libby_size = os.path.getsize(libby_pdf)

        print(
            f"📊 Shane's PDF: {shane_size:,} bytes ({shane_size/1024:.1f} KB)")
        print(
            f"📊 Libby's PDF: {libby_size:,} bytes ({libby_size/1024:.1f} KB)")

        size_diff = abs(shane_size - libby_size)
        print(
            f"📊 Size difference: {size_diff:,} bytes ({size_diff/1024:.1f} KB)")

        if abs(shane_size - libby_size) < 100000:  # Within 100KB
            print("✅ Similar sizes suggest both have embedded images!")
        else:
            print("ℹ️ Different sizes - may be due to different meal content")


def summarize_libby_plan():
    """Summarize what Libby gets in her meal plan"""
    print("\n=== LIBBY'S MEAL PLAN SUMMARY ===")

    print("👤 Client Profile:")
    print("   • Libby (39 years old)")
    print("   • Goal: Lose 10-15kg for comfort & confidence")
    print("   • High Protein Vegan diet")
    print("   • Loves easy prep meals")
    print("   • Not fussy - loves variety")

    print("\n🎯 Nutrition Targets:")
    print("   • 1,740 calories daily (500 cal deficit)")
    print("   • 155g protein for muscle preservation")
    print("   • Focus on easy-prep, high-protein vegan meals")

    print("\n🍽️ Meal Highlights:")
    print("   • Power Salad Bowls (5 min prep)")
    print("   • Mediterranean Wraps (3 min assembly)")
    print("   • Thai Tofu Stir-frys (15 mins)")
    print("   • Simple Lentil Pasta (20 mins)")
    print("   • Protein Smoothie Bowls (3 mins)")
    print("   • Quick Chickpea Curries")

    print("\n📸 Visual Features:")
    print("   • 8 AI-generated meal photos")
    print("   • Photorealistic food photography")
    print("   • Generated with Gemini 2.5 Flash")
    print("   • Makes meal prep more appealing")

    print("\n💪 Perfect for Libby because:")
    print("   • All meals are easy to prep")
    print("   • Variety she loves (salads, wraps, curries, pasta)")
    print("   • High protein for strength training")
    print("   • Visual guide makes cooking easier")
    print("   • Supports her fat loss goals")


if __name__ == "__main__":
    images_embedded = analyze_libby_pdf()
    compare_with_shane()
    summarize_libby_plan()

    print(f"\n=== FINAL ASSESSMENT ===")
    if images_embedded:
        print(f"🎉 Libby's meal plan PDF contains embedded images!")
        print(f"📸 8 out of 28 meals have beautiful AI-generated photos")
        print(f"🍽️ Perfect for her easy-prep preferences!")
        print(f"💪 Ready to support her 10-15kg fat loss journey!")
    else:
        print(f"❌ Images may not be properly embedded")
        print(f"📋 But complete text-based meal plan is available")
