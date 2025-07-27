import os
import json
import base64
import asyncio
from pdf2image import convert_from_path
from PIL import Image
from io import BytesIO
from utils.openai import openai_vision_completion
from utils.schema_util import get_all_schema_keys

VISION_CACHE_FILE = "./json/vision_results.json"

def save_vision_results(vision_results):
    """Save vision results to cache file"""
    try:
        # Ensure json directory exists
        os.makedirs("json", exist_ok=True)
        with open(VISION_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(vision_results, f, indent=2, ensure_ascii=False)
        print(f"  💾 Vision results cached to {VISION_CACHE_FILE}")
    except Exception as e:
        print(f"  ⚠️  Failed to save vision cache: {e}")

def load_vision_results():
    """Load vision results from cache file"""
    if not os.path.exists(VISION_CACHE_FILE):
        return None
    
    try:
        with open(VISION_CACHE_FILE, 'r', encoding='utf-8') as f:
            vision_results = json.load(f)
        
        # Validate the structure
        if isinstance(vision_results, list) and len(vision_results) > 0:
            # Check if first item has expected structure
            first_item = vision_results[0]
            if isinstance(first_item, dict) and 'page_num' in first_item and 'fields' in first_item and 'extracted_data' in first_item:
                return vision_results
        
        print(f"  ⚠️  Invalid vision cache format, will regenerate")
        return None
        
    except Exception as e:
        print(f"  ⚠️  Failed to load vision cache: {e}")
        return None

def pdf_to_images(pdf_path, dpi=200):
    """Convert PDF to images at specified DPI"""
    try:
        print(f"  📄 Converting PDF to images at {dpi} DPI...")
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=dpi, fmt='jpeg')
        print(f"  ✅ Successfully converted {len(images)} pages to images")
        return images
    except Exception as e:
        print(f"  ❌ Failed to convert PDF to images: {e}")
        return []

def image_to_base64(image):
    """Convert PIL image to base64 string"""
    try:
        # Convert image to RGB if it's not already
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Save image to BytesIO buffer
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=95)
        buffer.seek(0)
        
        # Encode to base64
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return image_base64
    except Exception as e:
        print(f"  ❌ Failed to convert image to base64: {e}")
        return None

async def process_image_with_vision(image, page_num, all_fields):
    """Process a single image with OpenAI vision"""
    try:
        # Convert image to base64
        base64_image = image_to_base64(image)
        if not base64_image:
            return None
        
        # Create the prompt
        prompt = f"""
        check if the attached image contains any of the following fields:
        {all_fields}

        if it does, return the field name in the list.
        if it does not, return empty list.

        also return all the descriptive data in json form with
        include all the tables checkboxes and anyother thing dont leave anything

        if no fields are found, return extracted_data as empty json object as well

        return strictly in this format:
        {{
        "fields": [list of all the fields that are present in the text],
        "extracted_data": {{extracted data in json structure}}
        }}
        """
        
        print(f"  🤖 Processing page {page_num} with OpenAI vision...")
        
        # Call OpenAI vision API
        response = await openai_vision_completion(prompt, base64_image)
        
        # Parse the JSON response
        try:
            parsed_response = json.loads(response)
            
            # Validate response structure
            if not isinstance(parsed_response, dict):
                print(f"  ⚠️  Invalid response format for page {page_num}")
                return None
                
            fields = parsed_response.get('fields', [])
            extracted_data = parsed_response.get('extracted_data', {})
            
            # Ensure fields is a list
            if not isinstance(fields, list):
                fields = []
            
            # Ensure extracted_data is a dict
            if not isinstance(extracted_data, dict):
                extracted_data = {}
            
            return {
                "page_num": page_num,
                "fields": fields,
                "extracted_data": extracted_data,
                "has_relevant_fields": len(fields) > 0
            }
            
        except json.JSONDecodeError as e:
            print(f"  ⚠️  Failed to parse JSON response for page {page_num}: {e}")
            print(f"  Raw response: {response[:200]}...")
            return None
            
    except Exception as e:
        print(f"  ❌ Failed to process page {page_num} with vision: {e}")
        return None

async def process_pdf_with_vision(pdf_path, use_cache=True):
    """Process entire PDF with OpenAI vision"""
    
    # Check if we have valid cached results first (only if use_cache is True)
    if use_cache and os.path.exists(VISION_CACHE_FILE):
        print(f"  📋 Checking vision cache: {VISION_CACHE_FILE}")
        cached_results = load_vision_results()
        
        if cached_results and len(cached_results) > 0:
            print(f"  ✅ Using cached vision results: {len(cached_results)} pages")
            return cached_results
    elif not use_cache:
        print(f"  🚫 Vision cache disabled, will create new vision results")
    
    try:
        # Get all schema fields
        all_fields = get_all_schema_keys()
        print(f"  📊 Found {len(all_fields)} schema fields to check")
        
        # Convert PDF to images
        images = pdf_to_images(pdf_path)
        if not images:
            return []
        
        # Process each image
        results = []
        
        # Process images with a reasonable concurrency limit
        semaphore = asyncio.Semaphore(40)  # Limit to 3 concurrent requests
        
        async def process_single_image(image, page_num):
            async with semaphore:
                return await process_image_with_vision(image, page_num, all_fields)
        
        # Create tasks for all images
        tasks = []
        for i, image in enumerate(images):
            page_num = i + 1
            task = process_single_image(image, page_num)
            tasks.append(task)
        
        # Process all images concurrently
        print(f"  🔄 Processing {len(images)} images concurrently...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None results and exceptions
        valid_results = []
        for result in results:
            if isinstance(result, dict) and result is not None:
                valid_results.append(result)
            elif isinstance(result, Exception):
                print(f"  ⚠️  Exception in processing: {result}")
        
        # Sort results by page number
        valid_results.sort(key=lambda x: x['page_num'])
        
        print(f"  ✅ Successfully processed {len(valid_results)} pages")
        
        # Save results to cache only if use_cache is True
        if use_cache:
            save_vision_results(valid_results)
        else:
            print(f"  🚫 Vision cache disabled, results not saved")
        
        return valid_results
        
    except Exception as e:
        print(f"  ❌ Failed to process PDF with vision: {e}")
        return []

def convert_vision_to_ocr_format(vision_results):
    """Convert vision results to OCR format for compatibility with existing pipeline"""
    ocr_format = []
    
    for result in vision_results:
        if not isinstance(result, dict):
            continue
            
        page_num = result.get('page_num', 0)
        extracted_data = result.get('extracted_data', {})
        
        # Convert extracted data to text format
        text = ""
        if isinstance(extracted_data, dict):
            # Convert JSON data to readable text
            text = json.dumps(extracted_data, indent=2, ensure_ascii=False)
        elif isinstance(extracted_data, str):
            text = extracted_data
        
        word_count = len(text.split()) if text else 0
        
        ocr_format.append({
            "page_num": page_num,
            "text": text,
            "word_count": word_count
        })
    
    return ocr_format

def get_relevant_pages_from_vision(vision_results):
    """Extract relevant pages from vision results in the format expected by analyze_relevant_pages_async"""
    relevant_pages = {}
    
    for result in vision_results:
        if not isinstance(result, dict):
            continue
            
        page_num = result.get('page_num', 0)
        fields = result.get('fields', [])
        has_relevant_fields = result.get('has_relevant_fields', False)
        extracted_data = result.get('extracted_data', {})
        
        if has_relevant_fields and len(fields) > 0:
            page_key = f"page_{page_num}"
            relevant_pages[page_key] = {
                "page_num": page_num,
                "is_relevant": True,
                "reason": f"AI determined: {{'fields': {fields}}}",
                "original_text": json.dumps(extracted_data, indent=2, ensure_ascii=False) if extracted_data else ""
            }
    
    return relevant_pages 