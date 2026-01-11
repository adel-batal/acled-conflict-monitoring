from pydantic import BaseModel, Field


class FeedbackIn(BaseModel):
    country: str = Field(min_length=1, max_length=50)
    feedback: str = Field(min_length=1, max_length=2000)


class FeedbackOut(BaseModel):
    id: int
    conflict_data_id: int
