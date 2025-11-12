#!/usr/bin/env python3
"""Test image generation with Vertex AI enabled"""

import os
from utils import maybe_generate_meal_image

def main():
    # Set your API key with Vertex AI enabled
    api_key = "AIzaSyAw2wJXX21rah4bx4IldV1RF5vjpsN3ET4"
    
    os.environ["ENABLE_MEAL_IMAGES"] = "1"
    os.environ["GOOGLE_API_KEY"] = api_key
    os.environ["GEMINI_API_KEY"] = api_key
    
    print("=== TESTING IMAGE GENERATION WITH VERTEX AI ===")
    print(f"API Key: {api_key[:20]}...")
    print()
    
    # Clear any cached images to force fresh generation
    import shutil
    if os.path.exists("test_vertex_images"):
        shutil.rmtree("test_vertex_images")
    
    # Test image generation with a simple meal
    print("Testing image generation with Vertex AI...")
    
    meal_name = "High-Protein Greek Yogurt Bowl"
    ingredients = "- 200g Greek Yogurt (low-fat)\n- 30g Whey Protein (vanilla)\n- 80g Mixed Berries\n- 20g Almonds\n- 10g Honey"
    preparation = "Whisk protein into yogurt. Top with berries, almonds, and a drizzle of honey."
    
    print(f"Testing meal: {meal_name}")
    
    try:
        image_path = maybe_generate_meal_image(
            meal_name,
            ingredients,
            preparation,
            "test_vertex_images"
        )
        
        if image_path:
            print(f"✅ SUCCESS! Image generated: {image_path}")
            if os.path.exists(image_path):
                size = os.path.getsize(image_path)
                print(f"✅ Image file exists: {size:,} bytes")
                print("🎉 Vertex AI image generation is working!")
            else:
                print("❌ Image path returned but file doesn't exist")
        else:
            print("❌ No image generated - checking what went wrong...")
            
            # Test the API access directly
            print("\nTesting Vertex AI models directly...")
            try:
                # Test new google-genai client
                from google import genai as new_genai
                from google.genai import types as new_genai_types
                client = new_genai.Client(api_key=api_key)
                
                print("✅ New google-genai client initialized")
                
                # Try imagen model
                try:
                    resp = client.models.generate_content(
                        model="imagen-3.0-generate-001",
                        contents=["A simple bowl of yogurt with berries"],
                        config=new_genai_types.GenerateContentConfig(
                            response_modalities=[new_genai_types.Modality.IMAGE],
                            candidate_count=1,
                        )
                    )
                    print("✅ Imagen model accessible!")
                except Exception as e:
                    print(f"❌ Imagen model error: {e}")
                    
            except Exception as e:
                print(f"❌ Google GenAI client error: {e}")
                
    except Exception as e:
        print(f"❌ Error during image generation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
