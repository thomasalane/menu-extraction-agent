from __future__ import annotations

import io
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from PIL import Image
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import MAX_TOKENS, MODEL_NAME
from parsing import extract_json_from_response, normalize_to_schema, repair_json
from prompts import SYSTEM_PROMPT, build_user_prompt
from schemas import LLMExtraction

load_dotenv()

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your_api_key_here":
            raise ValueError("GEMINI_API_KEY não configurada. Edite o arquivo .env.")
        _client = genai.Client(api_key=api_key)
    return _client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type(genai_errors.ServerError),
    reraise=True,
)
def _call_vision(image_bytes: bytes, user_prompt: str) -> tuple[str, LLMExtraction | None, float]:
    client = _get_client()
    start = time.time()

    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[pil_image, user_prompt],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=MAX_TOKENS,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=LLMExtraction,
        ),
    )

    duration = time.time() - start

    # Com response_schema o SDK já valida e desserializa em response.parsed.
    # Fica None se a resposta foi truncada ou não bateu com o schema.
    parsed = response.parsed if isinstance(response.parsed, LLMExtraction) else None
    return response.text or "", parsed, duration


def extract_menu(image_bytes: bytes, filename: str) -> dict:
    user_prompt = build_user_prompt(filename)
    raw_text, parsed_obj, duration = _call_vision(image_bytes, user_prompt)

    if parsed_obj is not None:
        raw = parsed_obj.model_dump()
    else:
        # Fallback: structured output falhou (truncamento, etc.) — repara manualmente
        json_text = extract_json_from_response(raw_text)
        raw = repair_json(json_text)

    return normalize_to_schema(raw, {
        "model_used": MODEL_NAME,
        "filename": filename,
        "duration": duration,
        "raw_response_length": len(raw_text),
    })
