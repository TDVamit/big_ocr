import os
import asyncio
from modules.google_pdf_ocr import ocr_pdf
from modules.check_page_relevance import check_pages_relevance_with_ai
from modules.analyse_insurance_type import analyze_relevant_pages_async
import time
from utils.openai import tokens_used
import json

OCR_CACHE_FILE = "./json/ocr_results.json"  

price_per_million_tokens = {
    "gpt-4.1-nano":{
        "prompt":0.100,
        "completion":0.400 ,
        "cached":0.025
    },
    "gpt-4.1-mini":{
        "prompt":0.40,
        "completion":1.60,
        "cached":0.10
    }
}

def save_ocr_results(ocr_results):
    """Save OCR results to cache file"""
    try:
        # Ensure json directory exists
        os.makedirs("json", exist_ok=True)
        with open(OCR_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(ocr_results, f, indent=2, ensure_ascii=False)
        print(f"  💾 OCR results cached to {OCR_CACHE_FILE}")
    except Exception as e:
        print(f"  ⚠️  Failed to save OCR cache: {e}")

def load_ocr_results():
    """Load OCR results from cache file"""
    if not os.path.exists(OCR_CACHE_FILE):
        return None
    
    try:
        with open(OCR_CACHE_FILE, 'r', encoding='utf-8') as f:
            ocr_results = json.load(f)
        
        # Validate the structure
        if isinstance(ocr_results, list) and len(ocr_results) > 0:
            # Check if first item has expected structure
            first_item = ocr_results[0]
            if isinstance(first_item, dict) and 'page_num' in first_item and 'text' in first_item:
                return ocr_results
        
        print(f"  ⚠️  Invalid OCR cache format, will regenerate")
        return None
        
    except Exception as e:
        print(f"  ⚠️  Failed to load OCR cache: {e}")
        return None

async def extract_text_with_ocr_async(pdf_path, use_cache=True, pdf_images_path=None):
    """Extract text using Google Cloud Vision OCR with caching"""

    # STEP 1: Check if we have valid cached OCR results first (only if use_cache is True)
    if use_cache and os.path.exists(OCR_CACHE_FILE):
        print(f"  📋 Checking OCR cache: {OCR_CACHE_FILE}")
        cached_results = load_ocr_results()
        
        if cached_results and len(cached_results) > 0:
            return cached_results
    elif not use_cache:
        print(f"  🚫 Cache disabled, will create new OCR results")
        
    try:
        if pdf_images_path and os.path.exists(pdf_images_path) and use_cache:
            print(f"  🖼️  Using provided images from: {pdf_images_path}")
            # Use provided images path for OCR
            google_ocr_results = await ocr_pdf(local_pdf=pdf_path, batch_size=100, pdf_images_path=pdf_images_path)
        else:
            print(f"  🤖 Processing PDF with Google Cloud Vision OCR...")
            google_ocr_results = await ocr_pdf(local_pdf=pdf_path, batch_size=100)
        
        # Convert google_pdf_ocr format to our expected format
        all_results = []
        for page_key, page_data in google_ocr_results.items():
            page_num = page_data['page_number']
            text = page_data['text']
            
            # Clean text to prevent encoding issues
            if text:
                try:
                    # Ensure text is properly encoded
                    clean_text = text.encode('utf-8', errors='ignore').decode('utf-8')
                except UnicodeError:
                    clean_text = str(text).encode('ascii', errors='ignore').decode('ascii')
            else:
                clean_text = ""
            
            word_count = len(clean_text.split()) if clean_text else 0
            
            result = {
                "page_num": page_num,
                "text": clean_text,
                "word_count": word_count
            }
            all_results.append(result)


        # Sort results by page number
        all_results.sort(key=lambda x: x['page_num'])
        
        print(f"\n  📊 Google Cloud Vision OCR Summary: {len(all_results)} pages")

        # Save results only if use_cache is True
        if use_cache:
            save_ocr_results(all_results)
        else:
            print(f"  🚫 Cache disabled, OCR results not saved")

        return all_results
        
    except UnicodeEncodeError as e:
        print(f"  ❌ Encoding error in Google Cloud Vision OCR: {e}")
        print(f"  💡 This is usually caused by special characters in the PDF text")
        return []
    except Exception as e:
        print(f"  ❌ Google Cloud Vision OCR failed: {e}")
        return []



async def main_async(PDF_FILE = "input.pdf", use_cache=True, pdf_images_path=None, add_padding=True):
    """Main async processing function"""

    start_time = time.time()

    cache_status = "ENABLED" if use_cache else "DISABLED"
    images_status = "PROVIDED" if pdf_images_path else "NOT PROVIDED"
    padding_status = "ENABLED" if add_padding else "DISABLED"
    print(f"📄 PDF OCR + RELEVANCE CHECK + INSURANCE ANALYSIS PIPELINE (CACHE {cache_status}) (IMAGES {images_status}) (PADDING {padding_status})")

    if not os.path.exists(PDF_FILE):
        print(f"❌ Error: PDF file '{PDF_FILE}' not found!")
        return 0
    
    # Pass pdf_images_path to OCR function
    ocr_results = await extract_text_with_ocr_async(PDF_FILE, use_cache, pdf_images_path)
    
    if not ocr_results:
        print(f"❌ No OCR results obtained")
        return 0
    
    relevant_pages = await check_pages_relevance_with_ai(ocr_results)
    
    final_results = await analyze_relevant_pages_async(relevant_pages, ocr_results, add_padding)
    
    end_time = time.time()
    execution_time = end_time - start_time

    print(f"  💾 Final results saved to json/extracted_insurance_fields.json")
    print("\n" + "=" * 80)
    print("🎉 ADVANCED INSURANCE PROCESSING COMPLETE!")
    print("=" * 80)
    print(f"📊 PROCESSING STATISTICS:")
    print(f"  • Total pages processed: {len(ocr_results)}")
    print(f"  • Relevant pages found: {len(relevant_pages)}")
    print(f"  • Cache usage: {cache_status}")
    print(f"  • Images path: {images_status}")
    print(f"  • Page padding: {padding_status}")
    print(f"  • Execution time: {execution_time:.2f} seconds")
    prompt_charge = (tokens_used["gpt-4.1-nano"]["prompt_tokens"] * price_per_million_tokens["gpt-4.1-nano"]["prompt"] / 1000000) + (tokens_used["gpt-4.1-mini"]["prompt_tokens"] * price_per_million_tokens["gpt-4.1-mini"]["prompt"] / 1000000)
    completion_charge = (tokens_used["gpt-4.1-nano"]["completion_tokens"] * price_per_million_tokens["gpt-4.1-nano"]["completion"] / 1000000) + (tokens_used["gpt-4.1-mini"]["completion_tokens"] * price_per_million_tokens["gpt-4.1-mini"]["completion"] / 1000000)
    cached_charge = (tokens_used["gpt-4.1-nano"]["cached_tokens"] * price_per_million_tokens["gpt-4.1-nano"]["cached"] / 1000000) + (tokens_used["gpt-4.1-mini"]["cached_tokens"] * price_per_million_tokens["gpt-4.1-mini"]["cached"] / 1000000)
    ocr_charge = len(ocr_results) * 0.0015
    total_charge = prompt_charge + completion_charge + cached_charge + ocr_charge
    print(f"  • Prompt charge: ${prompt_charge:.6f}")
    print(f"  • Completion charge: ${completion_charge:.6f}")
    print(f"  • Cached charge: ${cached_charge:.6f}")
    print(f"  • OCR charge: ${ocr_charge:.6f}")
    print(f"  • Total charge: ${total_charge:.6f}")
    # Count categorized pages
    total_categorized = 0
    if isinstance(final_results, dict):
        for insurance_type, data in final_results.items():
            if not isinstance(data, dict) or "error" in data:
                continue
            print(f"  • {insurance_type}: Field extraction completed")
            total_categorized += 1
    
    print(f"  • Insurance types processed: {total_categorized}")  
    print(f"\n🚀 ADVANCED PIPELINE SUMMARY:")
    print(f"  • Stage 1: OCR extraction ✅")
    print(f"  • Stage 2: AI relevance check ✅ (Fast field matching)")
    print(f"  • Stage 3: Insurance categorization ✅ (Group by type)")
    print(f"  • Stage 4: Page padding ✅ (Add context pages)" if add_padding else f"  • Stage 4: Page padding ❌ (Disabled)")
    print(f"  • Stage 5: Field extraction ✅ (Type-specific schemas)")
    
    # Return total cost for frontend display
    return total_charge

def main():
    """Main entry point"""
    # Default behavior: use cache
    asyncio.run(main_async())
    
    # To disable cache, you can call:
    # asyncio.run(main_async(use_cache=False))
    
    # To specify both PDF file and cache setting:
    # asyncio.run(main_async("your_file.pdf", use_cache=False))

if __name__ == "__main__":
    import sys
    
    # Check for command line arguments
    use_cache = True
    pdf_file = "input.pdf"
    
    # Simple command line argument parsing
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg.lower() == "--no-cache":
                use_cache = False
                print("🚫 Cache disabled via command line argument")
            elif arg.endswith(".pdf"):
                pdf_file = arg
                print(f"📄 Using PDF file: {pdf_file}")
    
    asyncio.run(main_async(pdf_file, use_cache))