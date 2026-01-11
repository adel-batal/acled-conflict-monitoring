from pydantic import BaseModel, Field


class ConflictDeleteIn(BaseModel):
    country: str = Field(min_length=1, max_length=50)
    admin1: str = Field(min_length=1, max_length=50)
