from utils.schema_util import get_all_schema_keys
from utils.openai import open_ai_chat_completion
import json
import asyncio
from pydantic import BaseModel
import os
RELEVANCE_OUTPUT = "json/page_relevance.json"

CHEAP_MODEL = "gpt-4.1-mini"  

MAX_RETRIES = 3
RETRY_DELAY = 2.0
REQUEST_DELAY = 1.5
MAX_CONCURRENT_REQUESTS = 20

async def check_pages_relevance_with_ai(ocr_results):
    """AI-based relevance check for all pages"""
    
    all_fields = get_all_schema_keys()
    
    print(f"  🤖 AI checking {len(ocr_results)} pages using {CHEAP_MODEL}...")

    if os.path.exists(RELEVANCE_OUTPUT):
        with open(RELEVANCE_OUTPUT, 'r', encoding='utf-8') as f:
            all_relevant_pages = json.load(f)
    else:
        all_relevant_pages = await process_relevance_batch(ocr_results,all_fields)
    
    relevance_output = RELEVANCE_OUTPUT
    print(f"  💾 Saving AI relevance results to {relevance_output}...")
    
    with open(relevance_output, 'w', encoding='utf-8') as f:
        json.dump(all_relevant_pages, f, indent=2, ensure_ascii=False)
    
    return all_relevant_pages

async def process_relevance_batch(batch_pages, all_fields):
    """Process a single batch of AI relevance checks"""
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    batch_tasks = [
        check_page_relevance_async(page_data, all_fields, semaphore)
        for page_data in batch_pages
    ]
    
    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
    
    batch_relevant = {}
    relevant_count = 0
    
    for result in batch_results:
        if isinstance(result, Exception):
            print(f"    ❌ AI relevance check failed: {result}")
            continue
        
        page_key = f"page_{result['page_num']}"
        
        if result['is_relevant']:
            batch_relevant[page_key] = result
            relevant_count += 1
    
    
    return  batch_relevant

async def check_page_relevance_async(page_data, all_fields, semaphore):
    """Check if a page contains content relevant to any insurance fields using AI"""

    try:
        class RelevanceResponse(BaseModel):
            fields: list[str]

        async with semaphore:
            print(f"  🤖 AI checking page {page_data['page_num']} using {CHEAP_MODEL}...")

            page_num = page_data['page_num']
            text = page_data['text']
            
            if not text.strip():
                return {
                    "page_num": page_num,
                    "is_relevant": False,
                    "reason": "Empty or no readable text"
                }
            
            for attempt in range(MAX_RETRIES):
                try:
                    await asyncio.sleep(REQUEST_DELAY)
                    
                    types_list = str(all_fields)
                    
                    prompt = f"""

                        check if this, contains
                        {text}

                        data for any of these fields
                        fields to check for: {types_list}
                        ignore all the coverages forms and endorsements forms.

                        there will be examples given ignore them and focus on the document pages and real values.

                        return strictly in this format:
                        {{
                        fields : [list of all the fields that are present in the text]
                        }}
                        return empty list if no fields are present in the text

                        strictly return only the full json object, no extra text like (```json)or any other text
                    """

                    response = await  open_ai_chat_completion(model=CHEAP_MODEL, messages=[{"role": "user", "content": prompt}],basemodel=RelevanceResponse)
                    result = response if isinstance(response, dict) else json.loads(response)
                    if result.get("fields") != []:
                        is_relevant = True
                    else:
                        is_relevant = False
                    
                    return {
                        "page_num": page_num,
                        "is_relevant": is_relevant,
                        "reason": f"AI determined: {result}",
                        "original_text": text
                    }
                    
                except Exception as e:
                    print(f"  ⚠️  AI relevance check failed for page {page_num}, attempt {attempt + 1}: {e}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    else:
                        return {
                            "page_num": page_num,
                            "is_relevant": False,
                            "reason": f"AI relevance check failed - {str(e)}",
                            "error": str(e)
                        }
    except Exception as e:
        print(f"  ⚠️  AI relevance check failed for page {page_num}, attempt {attempt + 1}: {e}")
