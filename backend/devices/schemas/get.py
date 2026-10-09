import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DeviceResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    credential_id: str
    device_name: Optional[str] = None
    aaguid: Optional[str] = None
    sign_count: int
    created_at: datetime.datetime
    last_used_at: Optional[datetime.datetime] = None


class DeviceStatusResponseSchema(BaseModel):
    is_bound: bool
    has_device: bool
    device: Optional[DeviceResponseSchema] = None
    id: Optional[int] = None
    user_id: Optional[int] = None
    credential_id: Optional[str] = None
    device_name: Optional[str] = None
    aaguid: Optional[str] = None
    sign_count: Optional[int] = None
    created_at: Optional[datetime.datetime] = None
    last_used_at: Optional[datetime.datetime] = None


class MessageResponseSchema(BaseModel):
    success: bool = True
    message: str
