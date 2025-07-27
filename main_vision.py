import os
import asyncio
from modules.pdf_vision_ocr import process_pdf_with_vision, convert_vision_to_ocr_format, get_relevant_pages_from_vision
from modules.analyse_insurance_type import analyze_relevant_pages_async
import time
from utils.openai import tokens_used
import json

VISION_CACHE_FILE = "./json/vision_results.json"  

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

async def extract_and_analyze_with_vision(pdf_path, use_cache=True, pdf_images_path=None):
    """Extract text and analyze relevance using OpenAI vision"""
    
    if pdf_images_path and os.path.exists(pdf_images_path):
        print(f"  🖼️  Processing with provided images from: {pdf_images_path}")
    else:
        print(f"  🤖 Processing PDF with OpenAI Vision...")
    
    # Process PDF with vision - this replaces both OCR and relevance checking
    vision_results = await process_pdf_with_vision(pdf_path, use_cache, pdf_images_path)
    
    if not vision_results:
        print(f"  ❌ No results from vision processing")
        return [], []
    
    # Convert vision results to OCR format for compatibility with existing pipeline
    ocr_results = convert_vision_to_ocr_format(vision_results)
    
    # Extract relevant pages from vision results
    relevant_pages = get_relevant_pages_from_vision(vision_results)
    
    print(f"\n  📊 Vision Processing Summary:")
    print(f"  • Total pages processed: {len(vision_results)}")
    print(f"  • Pages with relevant fields: {len(relevant_pages)}")
    
    # Print relevant pages info
    if relevant_pages:
        page_nums = [str(data['page_num']) for data in relevant_pages.values()]
        print(f"  • Relevant pages: {', '.join(page_nums)}")
        for page_key, page_data in relevant_pages.items():
            # Extract fields from the reason string
            reason = page_data.get('reason', '')
            if 'fields' in reason:
                try:
                    # Extract fields list from the reason string
                    import re
                    fields_match = re.search(r"'fields': (\[.*?\])", reason)
                    if fields_match:
                        fields_str = fields_match.group(1)
                        fields_count = len(eval(fields_str))  # Convert string to list and count
                        print(f"    - Page {page_data['page_num']}: {fields_count} fields found")
                except:
                    print(f"    - Page {page_data['page_num']}: Fields detected")
    
    return ocr_results, relevant_pages

async def main_async(PDF_FILE = "input.pdf", use_cache=True, pdf_images_path=None, add_padding=True):
    """Main async processing function"""

    start_time = time.time()

    cache_status = "ENABLED" if use_cache else "DISABLED"
    images_status = "PROVIDED" if pdf_images_path else "NOT PROVIDED"
    padding_status = "ENABLED" if add_padding else "DISABLED"
    print(f"📄 PDF VISION OCR + RELEVANCE CHECK + INSURANCE ANALYSIS PIPELINE (CACHE {cache_status}) (IMAGES {images_status}) (PADDING {padding_status})")

    if not os.path.exists(PDF_FILE):
        print(f"❌ Error: PDF file '{PDF_FILE}' not found!")
        return 0
    
    # Process PDF with OpenAI vision (replaces both OCR and relevance checking)
    ocr_results, relevant_pages = await extract_and_analyze_with_vision(PDF_FILE, use_cache, pdf_images_path)
    
    if not ocr_results:
        print(f"❌ No OCR results obtained from vision processing")
        return 0
    
    if not relevant_pages:
        print(f"⚠️  No relevant pages found in the document")
        print(f"  • Total pages processed: {len(ocr_results)}")
        print(f"  • Consider checking if the document contains insurance-related content")
        return 0
    
    # Continue with existing insurance analysis pipeline
    final_results = await analyze_relevant_pages_async(relevant_pages, ocr_results, add_padding)
    
    end_time = time.time()
    execution_time = end_time - start_time

    print(f"  💾 Final results saved to extracted_insurance_fields.json")
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
    
    # Calculate costs
    prompt_charge = (tokens_used["gpt-4.1-nano"]["prompt_tokens"] * price_per_million_tokens["gpt-4.1-nano"]["prompt"] / 1000000) + (tokens_used["gpt-4.1-mini"]["prompt_tokens"] * price_per_million_tokens["gpt-4.1-mini"]["prompt"] / 1000000)
    completion_charge = (tokens_used["gpt-4.1-nano"]["completion_tokens"] * price_per_million_tokens["gpt-4.1-nano"]["completion"] / 1000000) + (tokens_used["gpt-4.1-mini"]["completion_tokens"] * price_per_million_tokens["gpt-4.1-mini"]["completion"] / 1000000)
    cached_charge = (tokens_used["gpt-4.1-nano"]["cached_tokens"] * price_per_million_tokens["gpt-4.1-nano"]["cached"] / 1000000) + (tokens_used["gpt-4.1-mini"]["cached_tokens"] * price_per_million_tokens["gpt-4.1-mini"]["cached"] / 1000000)
    total_charge = prompt_charge + completion_charge + cached_charge
    
    print(f"  • Prompt charge: ${prompt_charge:.6f}")
    print(f"  • Completion charge: ${completion_charge:.6f}")
    print(f"  • Cached charge: ${cached_charge:.6f}")
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
    print(f"  • Stage 1: Vision OCR + Relevance ✅ (Combined OpenAI Vision)")
    print(f"  • Stage 2: Insurance categorization ✅ (Group by type)")
    print(f"  • Stage 3: Page padding ✅ (Add context pages)" if add_padding else f"  • Stage 3: Page padding ❌ (Disabled)")
    print(f"  • Stage 4: Field extraction ✅ (Type-specific schemas)")
    
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