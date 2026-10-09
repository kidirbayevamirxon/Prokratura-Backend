from backend.devices.schemas.get import (
    DeviceResponseSchema,
    DeviceStatusResponseSchema,
    MessageResponseSchema,
)
from backend.devices.schemas.post import (
    RegisterOptionsRequestSchema,
    RegisterVerifyRequestSchema,
    LoginOptionsRequestSchema,
    LoginVerifyRequestSchema,
)
from backend.devices.schemas.patch import DeviceUpdateSchema

__all__ = [
    "DeviceResponseSchema",
    "DeviceStatusResponseSchema",
    "MessageResponseSchema",
    "RegisterOptionsRequestSchema",
    "RegisterVerifyRequestSchema",
    "LoginOptionsRequestSchema",
    "LoginVerifyRequestSchema",
    "DeviceUpdateSchema",
]
