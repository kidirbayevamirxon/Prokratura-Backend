from pydantic import BaseModel, Field


class MahallaCreateSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Mahalla name, e.g. 'Oqtepa MFY'")

