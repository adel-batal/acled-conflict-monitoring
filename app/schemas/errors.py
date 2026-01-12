from pydantic import BaseModel


class NotFoundOut(BaseModel):
    detail: str

class UnprocessableEntityOut(BaseModel):
    detail: str

class ConflictOut(BaseModel):
    detail: str

