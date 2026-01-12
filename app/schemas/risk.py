from decimal import Decimal
from pydantic import BaseModel


class RiskScoreOut(BaseModel):
    country_norm: str
    score: Decimal

class CalculatingOut(BaseModel):
    detail: str
