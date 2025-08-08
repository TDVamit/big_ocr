from utils.pdf_to_image_fast import pdf_to_image
from utils.openai import gemini_image_vision
import json
import asyncio
from asynciolimiter import StrictLimiter

limiter = StrictLimiter(rate=30)  

async def call_one(img_bytes):

    prompt = f"""
    Extract the text from the image with table in a structured json format so we can use it for analysis
    strictly do not miss any information if any info doent fit any field just retun in extra field
    also return full ocr with high accuracy :

    follow this json structure
    {{
    ocr_data : here data of ocr with 100% accuracy
    tables : here is object of structured all tables present in image
    }}
    """ 
    await limiter.wait()
    return await gemini_image_vision(
        prompt=prompt, img_bytes=img_bytes,
        model="gemini-2.5-flash-lite-preview-06-17"
    )

async def run_all(images):
    results = await asyncio.gather(*(call_one(img) for img in images))
    return results



async def vision_ocr(input_pdf_path,dpi=200):

    try:
    
        image_bytes = pdf_to_image(input_pdf_path,'image_bytes')

        ocr_results = await run_all(image_bytes)
        ocr_result =[]
        for i, ocr_text in enumerate(ocr_results):
            ocr_data={
                "page_num" : i+1,
                "text" : json.dumps(ocr_text),
                "word_count" : len(ocr_text['ocr_data']) if isinstance(ocr_text,dict) else len(ocr_text) 
            }
            ocr_result.append(ocr_data)
        return ocr_result
    except Exception as e:
        raise ValueError(f" something wrong with getting ocr data error :- {str(e)}")