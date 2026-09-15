from typing import Optional
from pydantic import BaseModel, Field


class MahallaUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    is_active: Optional[bool] = None

