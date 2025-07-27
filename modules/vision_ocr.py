from utils.pdf_to_image import pdf_to_images
from utils.openai import openai_vision_completion
import json
import asyncio

async def vision_ocr(input_pdf_path,dpi=200):

    try:
    
        base64_images = await pdf_to_images(input_pdf_path,dpi,'base64')

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

        ocr_result = []

        tasks = [
            openai_vision_completion(prompt, image)
            for image in base64_images
        ]
        ocr_results = await asyncio.gather(*tasks)

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