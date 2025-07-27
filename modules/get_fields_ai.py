import asyncio
from utils.schema_util import get_specific_fields_of_insurance_type
import json
from utils.openai import open_ai_chat_completion

MAX_RETRIES = 3
RETRY_DELAY = 2.0
REQUEST_DELAY = 0.5
MAX_TOKENS_PER_CHUNK = 30000

ANALYSIS_MODEL = "gpt-4.1-mini"   

def collect_data(src: dict, dst: dict):
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


async def extract_fields_by_insurance_type(padded_results, ocr_lookup):
    """Extract specific fields for each insurance type using the padded page sets"""
    
    final_results = {}
    extraction_tasks = []
    
    # Create all tasks first
    for insurance_type, pages_info in padded_results.items():
        # Create extraction task for each insurance type
        task = extract_fields_for_insurance_type(insurance_type, pages_info, ocr_lookup)
        extraction_tasks.append((insurance_type, task))
    
    print(f"  🔍 Extracting fields for {len(extraction_tasks)} insurance types in parallel...")
    
    # Execute all extraction tasks in parallel using asyncio.gather
    insurance_types = [item[0] for item in extraction_tasks]
    tasks = [item[1] for item in extraction_tasks]

                
    all_extracted_data = {}
    
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            for batch_result in result:
                if batch_result is None:
                    print(f"    ⚠️  Batch returned None result")
                    continue
                if isinstance(batch_result, dict) and "error" not in batch_result:
                    if batch_result["insurance_type"] not in all_extracted_data:
                        all_extracted_data[batch_result["insurance_type"]] = {"insurance_type": batch_result["insurance_type"], "extracted_fields":{}}
                    collect_data(batch_result["extracted_fields"],all_extracted_data[batch_result["insurance_type"]]["extracted_fields"])
                else:
                    print(f"    ⚠️  Batch failed: {batch_result}")   
                    
    except Exception as e:
        print(f"    ❌ Parallel field extraction failed: {e}")
        
    if all_extracted_data:
        return all_extracted_data
    else:
        return {"error": "No data extracted from images"}

def get_distance(page_num, page_group):
    for active_page_num in page_group:
        if abs(active_page_num-page_num) <= 10:
            return True
    return False
    

async def extract_fields_for_insurance_type(insurance_type, pages_info, ocr_lookup):
    """Extract specific fields for a single insurance type"""
    page_groups = []
    for page_key, page_info in pages_info.items():
        if isinstance(page_info, dict) and 'page_num' in page_info:
            page_num = page_info['page_num']
        else:
            try:
                page_num = int(page_key.split('_')[1])
            except (IndexError, ValueError):
                print(f"    ⚠️  Could not extract page number from {page_key}, skipping...")
                continue
        
        # Get OCR content for this page
        if page_key in ocr_lookup:
            ocr_data = ocr_lookup[page_key]
            if page_groups:
                group_found = False
                for page_group in page_groups:
                    if get_distance(page_num, page_group["page_nums"]):
                        page_group["page_nums"].append(page_num)
                        page_group["page_content"].append({
                            'page_num': page_num,
                            'text': ocr_data.get('text', '')
                        })
                        group_found = True
                        break
                if not group_found:
                    page_group={}
                    page_group["page_nums"] = [page_num]
                    page_group["page_content"] = [{
                        'page_num': page_num,
                        'text': ocr_data.get('text', '')
                    }]
                    page_groups.append(page_group)
            else:
                page_group={}
                page_group["page_nums"] = [page_num]
                page_group["page_content"] = [{
                'page_num': page_num,
                'text': ocr_data.get('text', ''),
                }]
                page_groups.append(page_group)
        else:
            print(f"    ⚠️  No OCR data found for {page_key} (page {page_num})")
    
    if not page_groups:
        return {"error": "No page content available"}
    
    
    # Get specific fields for this insurance type
    fields_schema = get_specific_fields_of_insurance_type(insurance_type)
    if not fields_schema:
        return {"error": f"No schema found for {insurance_type}"}
    
    
    try: 
        all_extracted_data= []
        for page_group in page_groups:
            all_extracted_data_per_type = {}
            tasks = []
            for page in page_group["page_content"]:
                tasks.append(extract_fields_with_ai(insurance_type, [page], fields_schema))
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for batch_result in results:
                    if batch_result is None:
                        print(f"    ⚠️  Batch returned None result")
                        continue
                    if isinstance(batch_result, dict) and "error" not in batch_result:
                        collect_data(batch_result,all_extracted_data_per_type)
                    else:
                        print(f"    ⚠️  Batch failed: {batch_result}")   
            except Exception as e:
                print(f" error in extract_fields_for_insurance_type {e}")
            all_extracted_data.append({"insurance_type": f"{insurance_type} : page Group {page_group["page_nums"]}", "extracted_fields": all_extracted_data_per_type})
        return all_extracted_data
    except Exception as e:
        return {"error": f"Field extraction failed: {e}"}

async def extract_fields_with_ai(insurance_type, pages_content, fields_schema):
    """Use AI to extract specific fields from pages"""
    print(f"  🤖 AI extracting fields for {insurance_type} using {ANALYSIS_MODEL}...")
    # Prepare pages text
    pages_text = ""
    for page_data in pages_content:
        page_num = page_data['page_num']
        text = page_data['text']
        padding_note = " [PADDING]" if page_data.get('is_padding', False) else ""
        pages_text += f"\nPage {page_num}{padding_note}:\n{text}\n"
    
    # Create schema description
    schema_desc = f"Extract specific fields for {insurance_type} insurance"
    schema_json = json.dumps(fields_schema, indent=2)
    
    prompt = f"""
You are extracting specific insurance information from document pages.

Insurance Type: {insurance_type}
Task: {schema_desc}

Schema to extract:
{schema_json}

Document Pages:
{pages_text}

INSTRUCTIONS:
1. Extract all available field values from the pages
2. Return data in the exact schema structure provided
3. Use null for fields not found in the document
4. Include confidence scores (0.0-1.0) for extracted values
5. Provide source page numbers for each extracted field with the key "source_page_numbers" with each extracted field

important: there will be examples givenignore them and focus on the document pages.

Return ONLY valid JSON matching the schema structure.
for a fields schema like this:
{{
fields_name:
    value:[] # array of values found on the page if different.
    confidence:0-1
    source_page_numbers:[]
}}
dont return fields where value is not found
"""

    for attempt in range(MAX_RETRIES):
        try:
            await asyncio.sleep(REQUEST_DELAY)
            
            response = await open_ai_chat_completion(model=ANALYSIS_MODEL, messages=[{"role": "user", "content": prompt}],basemodel=None)
            
            try:
                extracted_data = response if isinstance(response, dict) else json.loads(response)
                return extracted_data
            except json.JSONDecodeError as e:
                print(f"    ❌ {insurance_type}: JSON parsing error - {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                return {"error": f"JSON parsing failed: {e}"}
                
        except Exception as e:
            print(f"    ⚠️  {insurance_type}: Extraction error, attempt {attempt + 1} - {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            else:
                return {"error": f"Field extraction failed after {MAX_RETRIES} attempts: {e}"}