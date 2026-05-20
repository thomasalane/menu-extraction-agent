SYSTEM_PROMPT = """
You are a precise menu data extraction engine. Your sole function is to extract
structured data from restaurant menu images and return valid JSON.

CRITICAL RULES — follow exactly:

1. NULL RULE: If a field cannot be read clearly, set it to null.
   NEVER guess, infer, or omit a field. Omission is a critical failure.

2. PRICE RULE: price_raw must be copied character-for-character from the image,
   including the currency symbol, commas, and decimals exactly as printed.
   price_float must be the numeric value only (e.g., 32.90 not "32.90").
   If price is absent or illegible, both price_raw and price_float must be null.

3. CONFIDENCE RULE: For each field, report a score from 0.0 to 1.0:
   - 1.0 = you can read it with certainty
   - 0.8–0.9 = high confidence, minor ambiguity
   - 0.5–0.7 = partial legibility or inference involved
   - 0.0–0.4 = guessing, heavily blurred, or partial text
   When score < 0.7, you MUST provide a reason string explaining the uncertainty.

4. CATEGORY RULE: Use the menu's own category headers (e.g., "Entradas",
   "Sobremesas"). If no headers exist, use null. Do not invent categories.

5. EDGE CASES:
   - Blurry image: extract what you can, score low, note in extraction_notes
   - Handwritten menu: treat each legible word as high confidence, illegible as null
   - Partial menu (cut off): extract visible items only, note in extraction_notes
   - Combo/set menus: create one item per combo, describe components in description
   - Prices in ranges ("20-25"): set price_raw to "20-25", price_float to null

6. OUTPUT: Return ONLY the JSON object. No markdown fences, no explanation text
   before or after. The response must start with { and end with }.
""".strip()


def build_user_prompt(blur_score: float, filename: str) -> str:
    quality_note = ""
    if blur_score < BLUR_THRESHOLD_WARNING:
        quality_note = (
            f"\nNOTE: Blur detection indicates this image may be low quality "
            f"(blur score: {blur_score:.1f}). Apply conservative confidence "
            "scores and use null liberally."
        )

    return f"""Extract all menu items from this image.{quality_note}

Return a JSON object matching this exact structure:
{{
  "restaurant_name": "string or null",
  "currency_symbol": "string or null",
  "currency_code": "string or null",
  "extraction_notes": "string or null",
  "items": [
    {{
      "category": "string or null",
      "name": "string (required)",
      "description": "string or null",
      "price_raw": "string or null",
      "price_float": "number or null",
      "confidence_name": {{"score": 0.0, "reason": "string or null"}},
      "confidence_description": {{"score": 0.0, "reason": "string or null"}},
      "confidence_price": {{"score": 0.0, "reason": "string or null"}},
      "confidence_category": {{"score": 0.0, "reason": "string or null"}}
    }}
  ]
}}

Filename for reference: {filename}"""


BLUR_THRESHOLD_WARNING = 50.0
