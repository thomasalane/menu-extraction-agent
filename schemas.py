from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

from config import MODEL_NAME


class FieldConfidence(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reason: Optional[str] = None


class MenuItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    category: Optional[str] = None
    name: str
    description: Optional[str] = None
    price_raw: Optional[str] = None
    price_float: Optional[float] = None

    confidence_name: FieldConfidence
    confidence_description: FieldConfidence
    confidence_price: FieldConfidence
    confidence_category: FieldConfidence

    flags: list[str] = Field(default_factory=list)

    @field_validator("price_float", mode="before")
    @classmethod
    def coerce_price(cls, v):
        if v is None:
            return None
        try:
            return float(str(v).replace(",", "."))
        except (ValueError, TypeError):
            return None

    @model_validator(mode="after")
    def set_flags(self) -> "MenuItem":
        if self.confidence_name.score < 0.5 or self.confidence_price.score < 0.5:
            if "low_confidence" not in self.flags:
                self.flags.append("low_confidence")
        if self.price_raw and self.price_float is None:
            if "price_parse_failed" not in self.flags:
                self.flags.append("price_parse_failed")
        if not self.description:
            if "missing_description" not in self.flags:
                self.flags.append("missing_description")
        return self


class ExtractionMetadata(BaseModel):
    restaurant_name: Optional[str] = None
    currency_symbol: Optional[str] = None
    currency_code: Optional[str] = None
    extraction_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_used: str = MODEL_NAME
    image_filename: Optional[str] = None
    total_items_extracted: int = 0
    total_items_flagged: int = 0
    extraction_duration_seconds: Optional[float] = None
    raw_response_length: int = 0


class MenuExtractionResult(BaseModel):
    metadata: ExtractionMetadata
    items: list[MenuItem]
    extraction_notes: Optional[str] = None

    @model_validator(mode="after")
    def sync_counts(self) -> "MenuExtractionResult":
        self.metadata.total_items_extracted = len(self.items)
        self.metadata.total_items_flagged = sum(1 for item in self.items if item.flags)
        return self

    _COLUMNS = ["approved", "id", "category", "name", "description", "price_raw",
                "price_float", "conf_name", "conf_description", "conf_price",
                "conf_category", "flags"]

    def to_dataframe(self) -> pd.DataFrame:
        if not self.items:
            return pd.DataFrame(columns=self._COLUMNS)
        rows = []
        for item in self.items:
            rows.append({
                "approved": False,
                "id": item.id,
                "category": item.category or "",
                "name": item.name,
                "description": item.description or "",
                "price_raw": item.price_raw or "",
                "price_float": item.price_float,
                "conf_name": item.confidence_name.score,
                "conf_description": item.confidence_description.score,
                "conf_price": item.confidence_price.score,
                "conf_category": item.confidence_category.score,
                "flags": ", ".join(item.flags),
            })
        return pd.DataFrame(rows)
