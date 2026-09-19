from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class FileMetadataSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    filename: str
    file_url: str
    relative_path: str
    content_type: str
    size_bytes: int
    created_at: Optional[datetime] = None

