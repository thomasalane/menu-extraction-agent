from __future__ import annotations

import json
import re


def extract_json_from_response(text: str) -> str:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    text = re.sub(r"```\s*$", "", text).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in response: {text[:200]}")
    return text[start : end + 1]


def repair_json(text: str) -> dict:
    # Stage 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Stage 2: remove trailing commas before ] or }
    cleaned = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Stage 3: truncation recovery — find last complete item object
    # Walks backwards to find a } where exactly 1 { and 1 [ are still open
    # (meaning: inside the root object, inside the items array, after a full item)
    candidate = cleaned
    for i in range(len(candidate) - 1, -1, -1):
        if candidate[i] != "}":
            continue
        snippet = candidate[: i + 1]
        open_braces = snippet.count("{") - snippet.count("}")
        open_brackets = snippet.count("[") - snippet.count("]")
        if open_braces == 1 and open_brackets == 1:
            # Close items array then root object
            rebuilt = snippet + "]}"
            rebuilt = re.sub(r",\s*\]}", "]}", rebuilt)  # remove trailing comma before close
            try:
                result = json.loads(rebuilt)
                if isinstance(result, dict):
                    result["_truncated"] = True
                    return result
            except json.JSONDecodeError:
                pass
            break  # found the position but couldn't parse — stop searching

    # Stage 4: single-quote replacement
    try:
        return json.loads(text.replace("'", '"'))
    except json.JSONDecodeError:
        pass

    # Stage 5: last resort
    return {
        "items": [],
        "extraction_notes": f"JSON repair failed. Raw response (first 500 chars): {text[:500]}",
    }


def normalize_to_schema(raw: dict, metadata_override: dict) -> dict:
    metadata = {
        "restaurant_name": raw.get("restaurant_name"),
        "currency_symbol": raw.get("currency_symbol"),
        "currency_code": raw.get("currency_code"),
        "model_used": metadata_override.get("model_used", "gemini-2.5-flash"),
        "image_filename": metadata_override.get("filename"),
        "extraction_duration_seconds": metadata_override.get("duration"),
        "raw_response_length": metadata_override.get("raw_response_length", 0),
    }
    return {
        "metadata": metadata,
        "items": raw.get("items", []),
        "extraction_notes": raw.get("extraction_notes"),
    }
