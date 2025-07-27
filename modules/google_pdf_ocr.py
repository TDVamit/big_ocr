import time
import uuid
import json
import asyncio
import sys
from datetime import datetime, timezone
from google.cloud import storage, vision_v1
from google.api_core import exceptions
import os
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"json/service_account.json"

def safe_print(text):
    """Print text safely, handling Unicode encoding issues"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback to ASCII if Unicode fails
        safe_text = str(text).encode('ascii', errors='ignore').decode('ascii')
        print(safe_text)
    except Exception:
        # Last resort fallback
        print("[Text contains characters that cannot be displayed]")

def gen_unique_bucket_name(prefix: str) -> str:
    """Generates a globally unique, RFC-compliant GCS bucket name."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    unique = uuid.uuid4().hex[:8]
    name = f"{prefix}-{timestamp}-{unique}"
    #  ensure length ≤ 63, lowercase, no invalid chars
    return name[:63]

async def ensure_bucket(client, bucket_name, location="us"):
    try:
        loop = asyncio.get_event_loop()
        bucket = await loop.run_in_executor(None, client.get_bucket, bucket_name)
        safe_print(f"✅ Bucket exists: {bucket_name}")
    except exceptions.NotFound:
        loop = asyncio.get_event_loop()
        bucket = await loop.run_in_executor(None, lambda: client.create_bucket(bucket_name, location=location))
        safe_print(f"🆕 Created bucket: {bucket_name}")
    return bucket

async def upload_blob(bucket, local_path, blob_name):
    loop = asyncio.get_event_loop()
    blob = bucket.blob(blob_name)
    await loop.run_in_executor(None, blob.upload_from_filename, local_path)
    safe_print(f"↑ Uploaded {local_path} → gs://{bucket.name}/{blob_name}")

async def list_blobs(bucket, prefix=""):
    loop = asyncio.get_event_loop()
    blobs = await loop.run_in_executor(None, lambda: list(bucket.list_blobs(prefix=prefix)))
    return blobs

async def download_blob(blob, local_dest):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, blob.download_to_filename, local_dest)
    safe_print(f"↓ Downloaded gs://{blob.bucket.name}/{blob.name} → {local_dest}")

async def delete_blobs(bucket, prefix=""):
    blobs = await list_blobs(bucket, prefix)
    loop = asyncio.get_event_loop()
    
    # Delete all blobs in parallel
    delete_tasks = []
    for b in blobs:
        task = loop.run_in_executor(None, b.delete)
        delete_tasks.append(task)
    
    if delete_tasks:
        await asyncio.gather(*delete_tasks)
    
    safe_print(f"🗑 Deleted {len(blobs)} objects from gs://{bucket.name}/{prefix}")

async def ocr_async_pdf(input_uri, output_uri, batch_size=100):
    loop = asyncio.get_event_loop()
    client = vision_v1.ImageAnnotatorClient()
    gcs_source = vision_v1.GcsSource(uri=input_uri)
    input_conf = vision_v1.InputConfig(gcs_source=gcs_source, mime_type='application/pdf')
    feature = vision_v1.Feature(type=vision_v1.Feature.Type.DOCUMENT_TEXT_DETECTION)
    gcs_dest = vision_v1.GcsDestination(uri=output_uri)
    output_conf = vision_v1.OutputConfig(gcs_destination=gcs_dest, batch_size=batch_size)
    req = vision_v1.AsyncAnnotateFileRequest(
        features=[feature],
        input_config=input_conf,
        output_config=output_conf
    )
    safe_print(f"🔍 Starting OCR with batch_size={batch_size}")
    op = await loop.run_in_executor(None, lambda: client.async_batch_annotate_files(requests=[req]))
    safe_print(f"▶ OCR started: {op.operation.name}")
    return op

async def wait_for_op(op):
    safe_print("⏳ Waiting for OCR to complete...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: op.result(timeout=None))
    safe_print("✅ OCR completed.")

async def combine_json_files(json_files):
    """Combine multiple JSON files from Vision API into a single structured format"""
    safe_print(f"🔄 Combining {len(json_files)} JSON files...")
    
    all_responses = []
    
    # Read and parse all JSON files
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extract responses from this file
            if 'responses' in data:
                file_responses = data['responses']
                all_responses.extend(file_responses)
                safe_print(f"📄 {json_file}: {len(file_responses)} pages")
            else:
                safe_print(f"⚠️  {json_file}: No 'responses' key found")
            
        except Exception as e:
            safe_print(f"⚠️  Error reading {json_file}: {e}")
            continue
    
    safe_print(f"📄 Total found {len(all_responses)} page responses across all files")
    
    # Transform to desired structure
    combined_data = {}
    processed_pages = []
    
    for i, response in enumerate(all_responses):
        try:
            # Extract text with proper encoding handling
            text = ""
            if 'fullTextAnnotation' in response and 'text' in response['fullTextAnnotation']:
                raw_text = response['fullTextAnnotation']['text']
                # Clean text to prevent encoding issues
                if raw_text:
                    text = raw_text.encode('utf-8', errors='ignore').decode('utf-8')
            
            # Extract page number - Vision API starts from 0, so add 1
            page_number = i + 1  # Use index-based numbering
            if 'context' in response and 'pageNumber' in response['context']:
                page_number = response['context']['pageNumber']
            
            processed_pages.append(page_number)
            
            # Add to combined data
            combined_data[str(page_number)] = {
                "text": text,
                "page_number": page_number
            }
            
        except Exception as e:
            safe_print(f"⚠️  Error processing response {i}: {e}")
            continue
    
    safe_print(f"✅ Successfully processed pages: {min(processed_pages)}-{max(processed_pages)}" if processed_pages else "No pages processed")
    safe_print(f"✅ Combined data for {len(combined_data)} pages (expected all pages from PDF)")
    return combined_data

async def ocr_pdf(project = "gen-lang-client-0797033201", local_pdf = "input.pdf", prefix="mybucket", location="us", batch_size=100):
    st = storage.Client(project=project)

    in_name = gen_unique_bucket_name(prefix + "-in")
    out_name = gen_unique_bucket_name(prefix + "-out")

    in_bucket = await ensure_bucket(st, in_name, location)
    out_bucket = await ensure_bucket(st, out_name, location)

    await upload_blob(in_bucket, local_pdf, "input.pdf")

    in_uri = f"gs://{in_name}/input.pdf"
    out_prefix = "vision-output/"
    out_uri = f"gs://{out_name}/{out_prefix}"

    safe_print(f"🔍 Processing PDF with batch_size={batch_size} for large document support")
    op = await ocr_async_pdf(in_uri, out_uri, batch_size=batch_size)
    await wait_for_op(op)

    # Get all blobs with JSON files
    blobs = await list_blobs(out_bucket, prefix=out_prefix)
    json_blobs = [blob for blob in blobs if blob.name.endswith(".json")]
    
    safe_print(f"📥 Found {len(json_blobs)} JSON output files to download")
    safe_print(f"📥 Downloading {len(json_blobs)} JSON files in parallel...")
    
    # Download all JSON files in parallel using asyncio.gather
    download_tasks = []
    json_files = []
    for blob in json_blobs:
        local_file = blob.name.replace("/", "_")
        json_files.append(local_file)
        task = download_blob(blob, local_file)
        download_tasks.append(task)
    
    combined_data = {}
    
    if download_tasks:
        await asyncio.gather(*download_tasks)
        safe_print(f"✅ Downloaded {len(download_tasks)} JSON files in parallel")
        
        # Combine all JSON files into structured format
        combined_data = await combine_json_files(json_files)
        
        # Clean up downloaded JSON files
        loop = asyncio.get_event_loop()
        for json_file in json_files:
            try:
                await loop.run_in_executor(None, os.remove, json_file)
            except Exception as e:
                safe_print(f"⚠️  Could not remove {json_file}: {e}")
        
        safe_print(f"🗑️  Cleaned up {len(json_files)} temporary JSON files")
        
    else:
        safe_print("⚠️  No JSON files found to download")

    safe_print("\n🧹 Cleaning up buckets and contents...")
    await delete_blobs(in_bucket)
    await delete_blobs(out_bucket)
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, in_bucket.delete)
    await loop.run_in_executor(None, out_bucket.delete)
    safe_print(f"🗑 Buckets deleted: {in_name}, {out_name}")
    
    # Sort the combined data by page number before saving
    if combined_data:
        safe_print(f"📋 Sorting {len(combined_data)} pages by page number...")
        # Convert to list, sort by page number, then back to ordered dict
        sorted_pages = sorted(combined_data.items(), key=lambda x: int(x[0]))
        combined_data = {page_key: page_data for page_key, page_data in sorted_pages}
        safe_print(f"✅ Pages sorted from 1 to {len(combined_data)}")
    
    with open('combined.json', 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)

    
    safe_print(f"💾 Saved sorted combined data to combined.json ({len(combined_data)} pages)")
    return combined_data

if __name__ == '__main__':
    # For large PDFs (300+ pages), use larger batch_size
    asyncio.run(ocr_pdf(batch_size=10))
