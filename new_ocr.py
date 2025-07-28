from openai import OpenAI
import asyncio
from functools import partial
import base64
import os
from dotenv import load_dotenv
import time
import math
from PIL import Image
import tiktoken
import json
from utils.schema_util import get_all_schema_keys
from utils.openai import openai_vision_completion , tokens_used

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")



per_token_cost = {
    "gpt-4.1-mini":{
        "prompt":0.0000004,
        "completion":0.0000001,
        "cached":0.0000016
    },
    "gpt-4.1-nano":{
        "prompt":0.0000001,
        "completion":0.000000025,
        "cached":0.0000004
    }
}


async def main():
    image_path = r"pdf_images\page_1.jpg"
    model = "gpt-4.1-nano"
    start_time = time.time()
    base64_image = base64.b64encode(open(image_path, "rb").read()).decode("utf-8")
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
    response = await openai_vision_completion(prompt, base64_image, model=model)
    end_time = time.time()
    total_prompt_tokens = tokens_used[model]["prompt_tokens"]
    total_completion_tokens = tokens_used[model]["completion_tokens"]
    total_cached_tokens = tokens_used[model]["cached_tokens"]

    print("time taken", end_time - start_time)
    print(response)
    print("total cost ")
    print("total prompt tokens", total_prompt_tokens , "cost", total_prompt_tokens * per_token_cost[model]["prompt"])
    print("total completion tokens", total_completion_tokens, "cost", total_completion_tokens * per_token_cost[model]["completion"])
    print("total cached tokens", total_cached_tokens, "cost", total_cached_tokens * per_token_cost[model]["cached"])
    print("total cost", (total_prompt_tokens * per_token_cost[model]["prompt"]) + (total_completion_tokens * per_token_cost[model]["completion"]) + (total_cached_tokens * per_token_cost[model]["cached"]))
    print("total cost for 310 pages", ((total_prompt_tokens * per_token_cost[model]["prompt"]) + (total_completion_tokens * per_token_cost[model]["completion"]) + (total_cached_tokens * per_token_cost[model]["cached"])) * 310)

if __name__ == "__main__":
    asyncio.run(main())
