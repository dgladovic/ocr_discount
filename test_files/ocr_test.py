import os
import easyocr

# Note: We keep PIL imported because EasyOCR uses it internally, 
# but we removed the ImageDraw dependency since we are no longer generating the image.

def run_easyocr_test():
    """Initializes EasyOCR and runs it on a user-provided image."""
    
    # --- IMPORTANT: PLACE YOUR IMAGE HERE ---
    # The image file you want to analyze must be placed in the same directory 
    # as this script and named 'test_input.png'.
    image_path = "test_input.png" 

    if not os.path.exists(image_path):
        print(f"ERROR: Image file not found at '{image_path}'.")
        print("\nACTION REQUIRED:")
        print("Please place your input image file (e.g., a flyer or screenshot) in this directory and name it 'test_input.png'.")
        return

    print("--- 1. Initializing EasyOCR Reader (CPU Mode) ---")
    try:
        # Initializing with gpu=False is the key for CPU operation.
        reader = easyocr.Reader(['en'], gpu=False)
    except Exception as e:
        print(f"ERROR: Failed to initialize EasyOCR. Check PyTorch/dependencies. Error: {e}")
        return

    print(f"--- 2. Running OCR on {image_path} ---")
    
    # EasyOCR automatically loads the image from the path and runs the OCR
    # Result is a list of tuples: (bbox, text, confidence)
    results = reader.readtext(image_path)
    
    print("\n--- 3. OCR Results ---")
    if not results:
        print("No text detected.")
    
    detected_text = []
    for (bbox, text, conf) in results:
        print(f"Text: '{text}', Confidence: {conf:.4f}")
        detected_text.append(text)
        
    print(f"\n--- Combined Text Output ---")
    print(' '.join(detected_text))
    
if __name__ == "__main__":
    run_easyocr_test()
