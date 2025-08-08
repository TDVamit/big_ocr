import os
import asyncio
from mistralai import Mistral
import time
from dotenv import load_dotenv
load_dotenv()

async def upload_pdf(client: Mistral, pdf_path: str):
    """
    Uploads the PDF via async API and returns the file upload object.
    """
    with open(pdf_path, "rb") as f:
        file_payload = {"file_name": os.path.basename(pdf_path), "content": f}
        uploaded = await client.files.upload_async(file=file_payload, purpose="ocr")
    return uploaded

def get_signed_url(client: Mistral, file_id: str):
    """
    Retrieves a signed URL synchronously (no async alternative mentioned in docs).
    """
    return client.files.get_signed_url(file_id=file_id)

async def ocr_process(client: Mistral, signed_url: str, model: str, include_image_base64: bool):
    """
    Sends an async OCR request and returns the OCR result.
    """
    response = await client.ocr.process_async(
        model=model,
        document={
            "type": "document_url",
            "document_url": signed_url,
        },
        include_image_base64=include_image_base64,
    )
    return response

async def get_ocr_response(input_pdf_path: str, api_key: str = None):
    """
    High‑level function to upload PDF, sign it, run OCR, and return the response object.
    """
    if api_key is None:
        api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("Set MISTRAL_API_KEY env var or pass it as api_key.")
    async with Mistral(api_key=api_key) as client:
        upload = await upload_pdf(client, input_pdf_path)
        signed = get_signed_url(client, upload.id)
        ocr = await ocr_process(client, signed.url, model="mistral-ocr-latest", include_image_base64=True)
        return ocr

if __name__ == "__main__":
    async def main():
        input_path = "input.pdf"
        api_key = os.getenv("MISTRAL_API_KEY", "0PkMgvehfC1fIW0mKiwha9UjP6OnZmId")
        # Replace with your actual key, if not set in environment
        if not api_key:
            print("Please set the MISTRAL_API_KEY environment variable.")
            return
        start_time = time.time()
        ocr_result = await get_ocr_response(input_path, api_key=api_key)
        end_time = time.time()
        
        # if getattr(ocr_result, "pages", None):
        #     print(ocr_result.pages[0].markdown)
        # else:
        #     print(ocr_result)
        print(ocr_result)
        print(f"Time taken: {end_time - start_time} seconds")

    asyncio.run(main())
