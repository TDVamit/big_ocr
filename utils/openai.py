from openai import OpenAI
import asyncio
from functools import partial
import os
import json
import time
from google import genai
from google.genai import types

from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
tokens_used = {"gpt-4.1-nano":{
    "prompt_tokens":0,
    "completion_tokens":0,
    "cached_tokens":0
},
"gpt-4.1-mini":{
    "prompt_tokens":0,
    "completion_tokens":0,
    "cached_tokens":0
},
"gemini-2.5-flash-lite-preview-06-17":{
    "prompt_tokens":0,
    "completion_tokens":0,
    "cached_tokens":0
}
}

async def gemini_image_vision(model='gemini-2.5-flash-lite-preview-06-17',prompt='',img_bytes=None):
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    for attempt in range(MAX_RETRIES):
        try:

            time_0 = time.time()
            # Initialize client (assumes GOOGLE_CLOUD_PROJECT and location set)
            client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
            # Prepare content parts: inlineData + user text
            contents = [
                types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'),
                types.Part.from_text(text=prompt)
            ]


            response = await client.aio.models.generate_content(
                model=f"models/{model}",
                contents=[types.Content(parts=contents)],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )

            usage = response.usage_metadata

            prompt_tokens = usage.prompt_token_count if usage.prompt_token_count is not None else 0
            cached_tokens = usage.cached_content_token_count if usage.cached_content_token_count is not None else 0
            output_tokens = usage.candidates_token_count if usage.candidates_token_count is not None else 0

            tokens_used[model]["prompt_tokens"] += prompt_tokens
            tokens_used[model]["cached_tokens"] += cached_tokens
            tokens_used[model]["completion_tokens"] += output_tokens
            time_end =time.time()
            print("time taken per vision -",time_end-time_0)
            return response.text
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {RETRY_DELAY} seconds...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                print(f"All {MAX_RETRIES} attempts failed. Last error: {str(e)}")
                raise


async def open_ai_chat_completion(model, messages, basemodel):
    MAX_RETRIES = 3         
    RETRY_DELAY = 2.0

    for attempt in range(MAX_RETRIES):
        try:
            print(f"Attempt {attempt + 1} of {MAX_RETRIES} for {model}")
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            if basemodel is not None:
                fn = partial(
                            client.beta.chat.completions.parse,
                            model=model,
                            messages=messages,
                            response_format=basemodel
                        )
                
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, fn)
                
                response = response.to_dict()
                prompt_tokens = response["usage"]["prompt_tokens"]
                completion_tokens = response["usage"]["completion_tokens"]
                cached_tokens = response["usage"].get("prompt_tokens_details", {}).get("cached_tokens", 0)

                tokens_used[model]["prompt_tokens"] += prompt_tokens
                tokens_used[model]["completion_tokens"] += completion_tokens
                tokens_used[model]["cached_tokens"] += cached_tokens

                return response["choices"][0]["message"]["content"]
            else:
                fn = partial(
                            client.beta.chat.completions.parse,
                            model=model,
                            messages=messages,
                            response_format={"type": "json_object"}
                        )
                
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(None, fn)
                response = response.to_dict()
                prompt_tokens = response["usage"]["prompt_tokens"]
                completion_tokens = response["usage"]["completion_tokens"]
                cached_tokens = response["usage"].get("prompt_tokens_details", {}).get("cached_tokens", 0)
                tokens_used[model]["prompt_tokens"] += prompt_tokens
                tokens_used[model]["completion_tokens"] += completion_tokens
                tokens_used[model]["cached_tokens"] += cached_tokens
                return json.loads(response["choices"][0]["message"]["content"])

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {RETRY_DELAY} seconds...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                print(f"All {MAX_RETRIES} attempts failed. Last error: {str(e)}")
                raise

async def openai_vision_completion(prompt, base64_image,model='gpt-4.1-nano'):
    """Process image with OpenAI vision model"""
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    time_0 = time.time()
    for attempt in range(MAX_RETRIES):
        try:
            # print(f"Vision API attempt {attempt + 1} of {MAX_RETRIES}")
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            fn = partial(
                client.chat.completions.create,
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"}
            )
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, fn)
            
            # Track token usage
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            
            # Handle cached tokens properly
            cached_tokens = 0
            if hasattr(response.usage, 'prompt_tokens_details'):
                prompt_details = response.usage.prompt_tokens_details
                if hasattr(prompt_details, 'cached_tokens'):
                    cached_tokens = prompt_details.cached_tokens

            tokens_used[model]["prompt_tokens"] += prompt_tokens
            tokens_used[model]["completion_tokens"] += completion_tokens
            tokens_used[model]["cached_tokens"] += cached_tokens
            time_end =time.time()
            print("time taken per vision -",time_end-time_0)
            return json.loads(response.choices[0].message.content)

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"Vision API attempt {attempt + 1} failed: {str(e)}. Retrying in {RETRY_DELAY} seconds...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                print(f"All {MAX_RETRIES} vision API attempts failed. Last error: {str(e)}")
                raise


