import os
from pdf2image import convert_from_path
from typing import Literal
import base64
from io import BytesIO

IMAGES_CACHE_DIR = 'temp_images'



async def pdf_to_images(pdf_path, dpi=200, return_type = Literal['local_path','pil','base64']):
    """Convert PDF to images and cache them, or use provided images"""
        
    os.makedirs(IMAGES_CACHE_DIR, exist_ok=True)
    
    
    try:
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=dpi, fmt='jpeg')
        
        if len(images) == 0:
            raise ValueError("❌ No pages found in PDF!")
            
        if return_type == 'pil':
            return images
        
        elif return_type == 'local_path':
            image_files = []
            for i, image in enumerate(images):
                page_num = i + 1
                filename = f"page_{page_num}.jpg"
                
                try:
                    filepath = os.path.join(IMAGES_CACHE_DIR, filename)
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    
                    image.save(filepath, format='JPEG', quality=100)
                except Exception as e:
                    print(f"  ⚠️  Failed to save image {filename}: {e}")
                
                image_files.append(filename)
            
            return image_files
        
        else :
            base64_images = []
            for img in images:
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                base64_images.append(img_base64)
            
            return base64_images
        
    except Exception as e:
        raise RuntimeError(f"❌ Failed to convert PDF to images: {e}\n💡 Make sure pdf2image and poppler are properly installed")
        