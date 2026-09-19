from pydantic import BaseModel, ConfigDict


class FileUploadResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_url: str
    relative_path: str
    filename: str
    original_name: str
    content_type: str
    size_bytes: int

