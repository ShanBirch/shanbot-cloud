#!/usr/bin/env python3
"""Test image generation with correct response modality specification"""

import os
import base64
from io import BytesIO
from PIL import Image


def test_with_new_genai_client():
    """Test using the newer google-genai client with proper modality specification"""
    api_key = "AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4"

    print("=== TESTING WITH NEW GOOGLE-GENAI CLIENT ===")

    try:
        from google import genai as new_genai
        from google.genai import types as new_genai_types

        client = new_genai.Client(api_key=api_key)
        print("✅ New google-genai client initialized")

        prompt = """Photorealistic food photo of a Greek yogurt bowl with mixed berries.
        
Camera angle: overhead (top-down 90°).
Natural daylight, shallow depth of field, realistic shadows.
Serve in a ceramic bowl on a wooden table.
Ingredients: 200g Greek yogurt, 100g mixed berries, 15g honey drizzle.
No text, no labels, no borders.
Food magazine quality."""

        # Test the image generation model that requires IMAGE modality
        model_name = "gemini-2.0-flash-preview-image-generation"

        print(f"🤖 Testing {model_name} with IMAGE modality...")

        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=[prompt],
                config=new_genai_types.GenerateContentConfig(
                    response_modalities=[new_genai_types.Modality.IMAGE],
                    candidate_count=1,
                )
            )

            if resp.candidates:
                for candidate in resp.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, "inline_data") and hasattr(part.inline_data, "data") and part.inline_data.data:
                                print("✅ SUCCESS! Image generated!")

                                # Save the image
                                os.makedirs("modality_test_images",
                                            exist_ok=True)
                                image_data = base64.b64decode(
                                    part.inline_data.data)
                                image = Image.open(BytesIO(image_data))
                                save_path = "modality_test_images/gemini_image_test.jpg"
                                image.save(save_path, "JPEG", quality=85)

                                print(f"💾 Saved: {save_path}")
                                print(f"📏 Size: {image.size}")
                                print(
                                    f"📊 File size: {len(image_data):,} bytes")

                                return True

            print("❌ No image data in response")
            return False

        except Exception as e:
            print(f"❌ Error with {model_name}: {e}")

            # Check if it's a quota issue
            if "quota" in str(e).lower() or "429" in str(e):
                print("⚠️ API quota exceeded - need to wait or upgrade plan")
                return False

            return False

    except ImportError:
        print("❌ New google-genai client not available")
        return False
    except Exception as e:
        print(f"❌ Error with new client: {e}")
        return False


def test_with_vertex_ai():
    """Test using Vertex AI directly"""
    print("\n=== TESTING WITH VERTEX AI CLIENT ===")

    try:
        # Try importing Vertex AI
        from google.cloud import aiplatform
        from vertexai.preview.vision_models import ImageGenerationModel

        print("✅ Vertex AI libraries available")

        # This would require proper Vertex AI setup with project ID, etc.
        print("ℹ️ Vertex AI requires additional setup (project ID, credentials)")
        print("ℹ️ This is typically for enterprise/production use")

        return False

    except ImportError:
        print("❌ Vertex AI libraries not installed")
        print("ℹ️ Would need: pip install google-cloud-aiplatform")
        return False


def check_quota_status():
    """Check the current API quota status"""
    print("\n=== CHECKING API QUOTA STATUS ===")

    api_key = "AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4"

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        # Try a simple text generation to see quota status
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("Hello, test quota status")

        if response and response.text:
            print("✅ Basic API access working")
            print("ℹ️ Quota issue may be specific to image generation models")
            return True
        else:
            print("❌ No response from API")
            return False

    except Exception as e:
        if "quota" in str(e).lower() or "429" in str(e):
            print("❌ API quota exceeded for all models")
            print("💡 Solutions:")
            print("   1. Wait for quota to reset (typically 24 hours)")
            print("   2. Upgrade to paid plan")
            print("   3. Use a different API key")
            return False
        else:
            print(f"❌ Other API error: {e}")
            return False


if __name__ == "__main__":
    print("Testing Google Gemini 2.5 Flash image generation...")

    # Check basic quota status first
    quota_ok = check_quota_status()

    if quota_ok:
        # Test with new client
        success = test_with_new_genai_client()

        if not success:
            # Test Vertex AI as fallback
            test_with_vertex_ai()

    if not quota_ok:
        print("\n💡 ALTERNATIVE SOLUTIONS:")
        print("1. Wait for quota reset (free tier limits)")
        print("2. Use a different Google API key")
        print("3. Integrate alternative image service (DALL-E, Stable Diffusion)")
        print("4. Generate meal plans without images for now")

        # Offer to generate without images
        print("\n❓ Would you like me to generate Shane's meal plan without images?")
        print("   We can add images later when quota is available.")
