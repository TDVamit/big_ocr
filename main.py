import os
import asyncio
from modules.google_pdf_ocr import ocr_pdf
from modules.check_page_relevance import check_pages_relevance_with_ai
from modules.analyse_insurance_type import analyze_relevant_pages_async
from modules.vision_ocr import vision_ocr
import time
from utils.openai import tokens_used
import json
from dotenv import load_dotenv
load_dotenv()

base_dir = os.path.dirname(os.path.realpath(__file__))
OCR_CACHE_FILE = os.path.join(base_dir, 'json', 'ocr_results.json')

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
    
    ocr_results = await vision_ocr(PDF_FILE,200)
    save_ocr_results(ocr_results)
    print("ocr result complete")
    if not ocr_results:
        print(f"❌ No OCR results obtained")
        return 0
    
    relevant_pages = await check_pages_relevance_with_ai(ocr_results)
    print("got relevent pages")
    final_results = await analyze_relevant_pages_async(relevant_pages, ocr_results, add_padding)
    print("print got final result")
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
    # ocr_charge = len(ocr_results) * 0.0015
    total_charge = prompt_charge + completion_charge + cached_charge 
    print(f"  • Prompt charge: ${prompt_charge:.6f}")
    print(f"  • Completion charge: ${completion_charge:.6f}")
    print(f"  • Cached charge: ${cached_charge:.6f}")
    # print(f"  • OCR charge: ${ocr_charge:.6f}")
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