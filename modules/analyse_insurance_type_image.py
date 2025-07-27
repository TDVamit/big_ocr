from utils.schema_util import get_insurance_types_from_schema, get_specific_fields_of_insurance_type
import json
import asyncio
from utils.openai import open_ai_chat_completion
from utils.page_helper import add_padding_pages, redistribute_common_pages
from modules.get_fields_ai_image import extract_fields_by_insurance_type_with_images
import os

ANALYSIS_MODEL = "gpt-4.1-mini"   
ANALYSIS_BATCH_SIZE = 20

MAX_RETRIES = 3
RETRY_DELAY = 2.0
REQUEST_DELAY = 1.5
MAX_CONCURRENT_REQUESTS = 10


def create_analysis_prompt_for_pages(pages_data, schema):
    """Create prompt for analyzing relevant pages with their full content"""

    pages_text = ""
    page_numbers = []

    for page_data in pages_data:
        page_num = page_data['page_num']
        text = page_data.get('original_text', '')
        page_numbers.append(page_num)
        pages_text += f"\nPage {page_num}:\n{text}\n"

    
    page_range = f"{min(page_numbers)}-{max(page_numbers)}" if len(page_numbers) > 1 else str(page_numbers[0])
    
    # Create a more concise schema description
    schema_summary = f"{schema}"
    # Create the full prompt
    prompt = f"""
        Analyze these insurance document pages to identify specific insurance types.

        INSTRUCTIONS:
        1. Identify the specific insurance type for each page
        2. Use exact type names from the available types
        3. Provide confidence (0.0-1.0) and brief notes
        4. Return info for ALL pages provided
        5. if you are not sure about the insurance type, return "Common" strictly
        6. strictly return the insurance type from the available types, no other text
        7. if you are not sure about the insurance type, return the closest match from the available types

        Available types: {schema_summary}

        Pages content (pages {page_range}):
        {pages_text}

        JSON format:
        {{
            "pages": {{
                "page_15": {{
                    "insurance_type": "Personal Auto" ( you can only choose from {schema_summary}),
                    "confidence": 0.95,
                    "notes": "Auto application with vehicle details"
                }}
            }}
        }}

        strictly insurance types from the available types, no other text
        Return ONLY valid JSON, no other text."""

    return prompt

async def analyze_relevant_pages_async_with_images(relevant_pages, ocr_results, image_files, images_cache_dir, add_padding=True):
    """Analyze only the relevant pages to determine insurance types and extract fields using images"""
    
    if not relevant_pages:
        print("  ⚠️  No relevant pages found to analyze")
        return {}
    
    schema = get_insurance_types_from_schema()
    
    ocr_lookup = {f"page_{data['page_num']}": data for data in ocr_results}
    
    relevant_pages_data = []
    for page_key, relevance_data in relevant_pages.items():
        page_num = relevance_data['page_num']
        # Get full OCR text for this page
        if page_key in ocr_lookup:
            full_ocr_data = ocr_lookup[page_key]
            page_data = {
                'page_num': page_num,
                'original_text': full_ocr_data.get('text', ''),
                'word_count': full_ocr_data.get('word_count', 0)
            }
            relevant_pages_data.append(page_data)
        
    # Same categorization process as original (using OCR text for categorization)
    categorized_results = await categorize_pages_by_insurance_type(relevant_pages_data, schema)
    
    # Conditionally add padding pages
    if add_padding:
        print("  📄 Adding padding pages...")
        padded_results = add_padding_pages(categorized_results, len(ocr_results))
    else:
        print("  🚫 Padding disabled, using only relevant pages")
        padded_results = categorized_results
    
    # Redistribute common pages
    redistributed_results = redistribute_common_pages(padded_results)
    
    # Extract fields using images instead of OCR text
    final_results = await extract_fields_by_insurance_type_with_images(redistributed_results, ocr_lookup, image_files, images_cache_dir)
    
    final_output = "./json/extracted_insurance_fields_image.json"
    print(f"  💾 Saving image-based field extraction results to {final_output}...")
    # Ensure json directory exists
    os.makedirs("json", exist_ok=True)
    with open(final_output, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, indent=2, ensure_ascii=False)
    
    return final_results

async def categorize_pages_by_insurance_type(relevant_pages_data, schema):
    """Categorize pages by insurance type"""
    
    # Create ALL batch tasks at once for parallel execution
    all_batch_tasks = []
    total_batches = (len(relevant_pages_data) + ANALYSIS_BATCH_SIZE - 1) // ANALYSIS_BATCH_SIZE
    
    for batch_start in range(0, len(relevant_pages_data), ANALYSIS_BATCH_SIZE):
        batch_end = min(batch_start + ANALYSIS_BATCH_SIZE, len(relevant_pages_data))
        batch_pages = relevant_pages_data[batch_start:batch_end]
        batch_num = (batch_start // ANALYSIS_BATCH_SIZE) + 1
        
        # Create a task for each batch
        batch_task = process_insurance_analysis_batch(batch_pages, batch_num, schema)
        all_batch_tasks.append(batch_task)
        
    # Execute ALL batches in parallel using asyncio.gather
    batch_results = await asyncio.gather(*all_batch_tasks, return_exceptions=True)
    
    # Combine all results and organize by insurance type
    categorized_by_type = {}
    successful_batches = 0
    
    for result in batch_results:
        if isinstance(result, Exception):
            print(f"    ❌ Categorization batch failed: {result}")
            continue
        
        batch_analysis, batch_num = result
        if batch_analysis:
            # Organize results by insurance type
            for page_key, page_analysis in batch_analysis.items():
                insurance_type = page_analysis.get('insurance_type', 'Common')
                data = get_specific_fields_of_insurance_type(insurance_type)
                if not data:
                    insurance_type = "Common"
                if insurance_type not in categorized_by_type:
                    categorized_by_type[insurance_type] = {}
                
                categorized_by_type[insurance_type][page_key] = page_analysis
            
            successful_batches += 1
    
    # Print categorization summary
    print(f"  📊 Categorization Complete:")
    for insurance_type, pages in categorized_by_type.items():
        # Extract page numbers from the pages
        page_numbers = []
        for page_key, page_info in pages.items():
            if isinstance(page_info, dict) and 'page_num' in page_info:
                page_numbers.append(page_info['page_num'])
            elif page_key.startswith('page_'):
                try:
                    page_num = int(page_key.split('_')[1])
                    page_numbers.append(page_num)
                except:
                    continue
        
        # Sort page numbers and format display
        page_numbers.sort()
    print(f"    • Successful batches: {successful_batches}/{total_batches}")
    
    return categorized_by_type


async def process_insurance_analysis_batch(batch_pages, batch_num, schema):
    
    print(f"  🤖 AI analyzing batch {batch_num} using {ANALYSIS_MODEL}...")
    for attempt in range(MAX_RETRIES):
        try:
            await asyncio.sleep(REQUEST_DELAY)
            
            prompt = create_analysis_prompt_for_pages(batch_pages, schema)
            
            response = await  open_ai_chat_completion(model=ANALYSIS_MODEL, messages=[{"role": "user", "content": prompt}],basemodel=None)            
            # Parse JSON response
            try:
                json_response = response if isinstance(response, dict) else json.loads(response)
                
                # Extract pages data
                if isinstance(json_response, dict) and "pages" in json_response:
                    result = json_response["pages"]
                else:
                    result = json_response
                
                return result, batch_num
                
            except json.JSONDecodeError as e:
    
                print(f"    ❌ JSON parsing error in categorization batch {batch_num}: {e} \n response: {response}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                return {}, batch_num
                
        except Exception as e:
            print(f"    ⚠️  Error in categorization batch {batch_num}, attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            else:
                print(f"    ❌ Failed to process categorization batch {batch_num} after {MAX_RETRIES} attempts")
                return {}, batch_num 