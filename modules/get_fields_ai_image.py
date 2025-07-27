import asyncio
from utils.schema_util import get_specific_fields_of_insurance_type
import json
from utils.openai import openai_vision_completion
import os
import base64
from PIL import Image

MAX_RETRIES = 3
RETRY_DELAY = 2.0
REQUEST_DELAY = 0.5
IMAGE_BATCH_SIZE = 10  # Process images in batches of 10

ANALYSIS_MODEL = "gpt-4.1-mini"   


def image_to_base64(image_path):
    """Convert image file to base64 string"""
    try:
        # Check if file exists
        if not os.path.exists(image_path):
            print(f"  ❌ Image file not found: {image_path}")
            return None
        
        # Check file size
        file_size = os.path.getsize(image_path)
        if file_size == 0:
            print(f"  ❌ Image file is empty: {image_path}")
            return None
        
        with Image.open(image_path) as image:
            # Get original format info
            original_format = image.format
            original_mode = image.mode
            
            # Convert image to RGB if it's not already
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert PIL image to base64 string
            from io import BytesIO
            buffer = BytesIO()
            
            # Determine output format based on file extension
            file_ext = os.path.splitext(image_path)[1].lower()
            if file_ext in ['.png']:
                # For PNG files, save as PNG to preserve quality
                image.save(buffer, format='PNG')
            else:
                # For JPG and other formats, save as JPEG
                image.save(buffer, format='JPEG', quality=95)
            
            buffer.seek(0)
            
            # Encode to base64
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Validate base64 string
            if not image_base64:
                print(f"  ❌ Generated empty base64 string for: {image_path}")
                return None
            
            return image_base64
            
    except FileNotFoundError:
        print(f"  ❌ Image file not found: {image_path}")
        return None
    except PermissionError:
        print(f"  ❌ Permission denied accessing image: {image_path}")
        return None
    except Image.UnidentifiedImageError:
        print(f"  ❌ Cannot identify image format: {image_path}")
        return None
    except Exception as e:
        print(f"  ❌ Failed to convert image {image_path} to base64: {e}")
        return None

async def extract_fields_by_insurance_type_with_images(padded_results, ocr_lookup, image_files, images_cache_dir):
    """Extract specific fields for each insurance type using images instead of OCR text"""
    
    final_results = {}
    extraction_tasks = []
    
    # Create all tasks first
    for insurance_type, pages_info in padded_results.items():
        # Create extraction task for each insurance type
        task = extract_fields_for_insurance_type_with_images(insurance_type, pages_info, ocr_lookup, image_files, images_cache_dir)
        extraction_tasks.append((insurance_type, task))
    
    print(f"  🔍 Extracting fields for {len(extraction_tasks)} insurance types using images in parallel...")
    
    # Execute all extraction tasks in parallel using asyncio.gather
    insurance_types = [item[0] for item in extraction_tasks]
    tasks = [item[1] for item in extraction_tasks]
    
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            insurance_type = insurance_types[i]
            if isinstance(result, Exception):
                print(f"    ❌ Image-based field extraction failed for {insurance_type}: {result}")
                final_results[insurance_type] = {"error": str(result)}
            else:
                final_results[insurance_type] = result
                
    except Exception as e:
        print(f"    ❌ Parallel image-based field extraction failed: {e}")
        # Fallback to sequential processing
        for insurance_type, task in extraction_tasks:
            try:
                extracted_fields = await task
                final_results[insurance_type] = extracted_fields
            except Exception as task_error:
                print(f"    ❌ Image-based field extraction failed for {insurance_type}: {task_error}")
                final_results[insurance_type] = {"error": str(task_error)}
    
    return final_results

async def extract_fields_for_insurance_type_with_images(insurance_type, pages_info, ocr_lookup, image_files, images_cache_dir):
    """Extract specific fields for a single insurance type using images"""
    
    # Collect page numbers for this insurance type
    page_numbers = []
    for page_key, page_info in pages_info.items():
        if isinstance(page_info, dict) and 'page_num' in page_info:
            page_num = page_info['page_num']
        else:
            try:
                page_num = int(page_key.split('_')[1])
            except (IndexError, ValueError):
                print(f"    ⚠️  Could not extract page number from {page_key}, skipping...")
                continue
        page_numbers.append(page_num)
    
    if not page_numbers:
        return {"error": "No page numbers available"}
    
    # Validate inputs
    if not image_files:
        return {"error": "No image files provided"}
    
    if not images_cache_dir or not os.path.exists(images_cache_dir):
        return {"error": f"Images directory not found: {images_cache_dir}"}
    
    # Find corresponding image files - handle both PNG and JPG with different naming patterns
    relevant_images = []
    missing_pages = []
    
    for page_num in page_numbers:
        image_found = False
        
        # Try different image file patterns
        possible_filenames = [
            f"page_{page_num:04d}.png",  # Format: page_0001.png (Streamlit frontend)
            f"page_{page_num}.jpg",      # Format: page_1.jpg (cache)
            f"page_{page_num}.png",      # Format: page_1.png (alternative)
            f"page_{page_num:03d}.png",  # Format: page_001.png (3-digit)
            f"page_{page_num:02d}.png",  # Format: page_01.png (2-digit)
        ]
        
        for filename in possible_filenames:
            if filename in image_files:
                image_path = os.path.join(images_cache_dir, filename)
                if os.path.exists(image_path):
                    try:
                        # Verify the image can be opened
                        with Image.open(image_path) as test_img:
                            pass  # Just test if it opens
                        
                        relevant_images.append({
                            'page_num': page_num,
                            'image_path': image_path,
                            'filename': filename
                        })
                        image_found = True
                        break
                    except Exception as e:
                        print(f"    ⚠️  Image {filename} exists but can't be opened: {e}")
        
        if not image_found:
            missing_pages.append(page_num)
    
    if not relevant_images:
        print(f"    ❌ No corresponding images found for {insurance_type}")
        print(f"    🔍 Looking for pages: {page_numbers}")
        print(f"    📁 Available images: {image_files[:10]}{'...' if len(image_files) > 10 else ''}")
        print(f"    📂 Images directory: {images_cache_dir}")
        
        # Try to list actual files in directory for debugging
        try:
            actual_files = os.listdir(images_cache_dir)
            print(f"    📋 Actual files in directory: {actual_files[:10]}{'...' if len(actual_files) > 10 else ''}")
        except Exception as e:
            print(f"    ❌ Can't list directory contents: {e}")
        
        return {"error": f"No corresponding images found. Looking for pages {page_numbers}, found {len(image_files)} images in {images_cache_dir}"}
    
    if missing_pages:
        print(f"    ⚠️  Missing images for pages: {missing_pages}")
    
    print(f"    🖼️  Processing {len(relevant_images)} images for {insurance_type} (missing {len(missing_pages)} pages)")
    
    # Get specific fields for this insurance type
    fields_schema = get_specific_fields_of_insurance_type(insurance_type)
    if not fields_schema:
        return {"error": f"No schema found for {insurance_type}"}
    
    try:
        extracted_data = await extract_fields_with_ai_images(insurance_type, relevant_images, fields_schema)
        return extracted_data
    except Exception as e:
        print(f"    ❌ Image-based field extraction failed for {insurance_type}: {e}")
        return {"error": f"Image-based field extraction failed: {e}"}

async def extract_fields_with_ai_images(insurance_type, relevant_images, fields_schema):
    """Use AI to extract specific fields from images in batches of 10"""
    print(f"  🤖 AI extracting fields for {insurance_type} using images in batches of {IMAGE_BATCH_SIZE}...")
    
    # Sort images by page number
    relevant_images.sort(key=lambda x: x['page_num'])
    
    # Process images in batches of 10
    all_extracted_data = {}
    total_batches = (len(relevant_images) + IMAGE_BATCH_SIZE - 1) // IMAGE_BATCH_SIZE
    
    # Create ALL batch tasks at once for parallel execution
    all_batch_tasks = []
    
    for batch_start in range(0, len(relevant_images), IMAGE_BATCH_SIZE):
        batch_end = min(batch_start + IMAGE_BATCH_SIZE, len(relevant_images))
        batch_images = relevant_images[batch_start:batch_end]
        batch_num = (batch_start // IMAGE_BATCH_SIZE) + 1
        
        print(f"    📸 Processing image batch {batch_num}/{total_batches} ({len(batch_images)} images)")
        
        # Create task for this batch
        batch_task = process_image_batch_for_fields(batch_images, insurance_type,fields_schema, batch_num)
        all_batch_tasks.append(batch_task)
    
    # Execute ALL batches in parallel using asyncio.gather
    batch_results = await asyncio.gather(*all_batch_tasks)

    def collect_data(src: dict, dst: dict):
        """
        Recursively merge two nested field-dictionaries.

        • If we are at a leaf (dict containing the key 'value'), merge the
          value-arrays, confidence (take the higher) and page lists.
        • Otherwise continue recursion.
        """
        if not isinstance(src, dict) or not isinstance(dst, dict):
            return
            
        for key, val in src.items():
            if val is None:
                continue  # Skip None values
                
            # Leaf node – contains the actual field info
            if isinstance(val, dict) and 'value' in val:
                if key in dst:
                    # merge/append without duplicating
                    dst_val = dst[key]
                    if dst_val is None:
                        dst[key] = val
                        continue
                        
                    # Safely get values with defaults
                    src_value = val.get('value', []) or []
                    dst_value = dst_val.get('value', []) or []
                    src_pages = val.get('source_page_numbers', []) or []
                    dst_pages = dst_val.get('source_page_numbers', []) or []
                    
                    # Ensure values are lists
                    if not isinstance(src_value, list):
                        src_value = [src_value] if src_value is not None else []
                    if not isinstance(dst_value, list):
                        dst_value = [dst_value] if dst_value is not None else []
                    if not isinstance(src_pages, list):
                        src_pages = [src_pages] if src_pages is not None else []
                    if not isinstance(dst_pages, list):
                        dst_pages = [dst_pages] if dst_pages is not None else []
                    
                    dst_val['value'] = list(dict.fromkeys(dst_value + src_value))
                    dst_val['confidence'] = max(dst_val.get('confidence', 0) or 0, val.get('confidence', 0) or 0)
                    dst_val['source_page_numbers'] = list(dict.fromkeys(dst_pages + src_pages))
                else:
                    dst[key] = val
            # Container – keep recursing
            elif isinstance(val, dict):
                if key not in dst:
                    dst[key] = {}
                elif dst[key] is None:
                    dst[key] = {}
                collect_data(val, dst[key])
            else:
                # primitive (shouldn't really happen in schema, but keep for safety)
                dst[key] = val
                
    # Process results from all batches
    for batch_result in batch_results:
        if batch_result is None:
            print(f"    ⚠️  Batch returned None result")
            continue
        if isinstance(batch_result, dict) and "error" not in batch_result:
            collect_data(batch_result,all_extracted_data)
        else:
            print(f"    ⚠️  Batch failed: {batch_result}")
    
    # Combine all batch results into final structure
    if all_extracted_data:
        # Organize by schema structure
        final_result = {
            "insurance_type": insurance_type,
            "total_pages_processed": len(relevant_images),
            "extracted_fields": all_extracted_data,
            "processing_method": "image_batch_processing"
        }
        return final_result
    else:
        return {"error": "No data extracted from images"}

async def process_image_batch_for_fields(batch_images, insurance_type,fields_schema, batch_num):
    """Process a batch of images to extract fields"""

    schema_json = json.dumps(fields_schema, indent=2)
 
    page_info = []
    for img_data in batch_images:
        page_info.append(f"Page {img_data['page_num']}")
    pages_description = ", ".join(page_info)
    
    # Create the prompt
    prompt = f"""
You are extracting specific insurance information from document images.

Insurance Type: {insurance_type}
Pages: {pages_description}

Schema to extract:
{schema_json}


INSTRUCTIONS:
1. Extract all available field values from ALL the images provided
2. Return data in the exact schema structure provided
3. Use null for fields not found in any of the images
4. Include confidence scores (0.0-1.0) for extracted values
5. Provide source page numbers for each extracted field
6. Process all images as a cohesive document set

Return ONLY valid JSON matching the schema structure.
for a fields schema like this:
{{
fields_name:
    value:[] # array of values found on the page if different.
    confidence:0-1
    source_page_numbers:[]
}}
"""

    for attempt in range(MAX_RETRIES):
        try:
            await asyncio.sleep(REQUEST_DELAY)

            first_image = batch_images[0]
            base64_image = image_to_base64(first_image['image_path'])
            
            if not base64_image:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                return {"error": f"Failed to convert image to base64 in batch {batch_num}"}
            
            response = await openai_vision_completion(prompt, base64_image)
            print(f"    🔍 {insurance_type} batch {batch_num}: Response - {response}")
            
            try:
                extracted_data = response if isinstance(response, dict) else json.loads(response)
                print(f"    🔍 {insurance_type} batch {batch_num}: Extracted data - {extracted_data}")
                return extracted_data
            except json.JSONDecodeError as e:
                print(f"    ❌ {insurance_type} batch {batch_num}: JSON parsing error - {e} - raw response: {response}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                return {"error": f"JSON parsing failed in batch {batch_num}: {e}"}
                
        except Exception as e:
            print(f"    ⚠️  {insurance_type} batch {batch_num}: Extraction error, attempt {attempt + 1} - {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            else:
                return {"error": f"Image field extraction failed after {MAX_RETRIES} attempts in batch {batch_num}: {e}"}

# Alternative implementation for multiple images per batch (if needed)
async def process_multiple_images_batch(batch_images, insurance_type, fields_schema, batch_num):
    """Process multiple images in a batch - each image separately"""
    
    batch_results = {}
    
    # Process each image in the batch
    for img_data in batch_images:
        page_num = img_data['page_num']
        image_path = img_data['image_path']
        
        # Convert image to base64
        base64_image = image_to_base64(image_path)
        if not base64_image:
            batch_results[f"page_{page_num}"] = {"error": "Failed to convert image"}
            continue
        
        # Create prompt for single image
        schema_json = json.dumps(fields_schema, indent=2)
        prompt = f"""
Extract specific insurance information from this document image.

Insurance Type: {insurance_type}
Page: {page_num}

Schema to extract:
{schema_json}

INSTRUCTIONS:
1. Extract all available field values from the image
2. Return data in the exact schema structure provided
3. Use null for fields not found in the image
4. Include confidence scores (0.0-1.0) for extracted values

Return ONLY valid JSON matching the schema structure."""

        try:
            response = await openai_vision_completion(prompt, base64_image)
            extracted_data = response if isinstance(response, dict) else json.loads(response)
            batch_results[f"page_{page_num}"] = extracted_data
        except Exception as e:
            print(f"    ⚠️  Failed to process page {page_num}: {e}")
            batch_results[f"page_{page_num}"] = {"error": str(e)}
    
    return batch_results 