from typing import Optional
from pydantic import BaseModel


class DeviceUpdateSchema(BaseModel):
    device_name: Optional[str] = None
