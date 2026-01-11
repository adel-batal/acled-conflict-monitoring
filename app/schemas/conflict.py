from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ConflictRowOut(BaseModel):
    admin1_raw: str
    population: Optional[int] = None
    events: int = Field(ge=0)
    score: Decimal


class ConflictCountryGroupOut(BaseModel):
    country_raw: str
    rows: list[ConflictRowOut]


class ConflictDataPageOut(BaseModel):
    page: int
    per_page: int
    countries: list[ConflictCountryGroupOut]
