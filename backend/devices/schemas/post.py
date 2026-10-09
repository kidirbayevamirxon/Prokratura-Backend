from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, ConfigDict


class RegisterOptionsRequestSchema(BaseModel):
    pass


class RegisterVerifyRequestSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    credential: Optional[Union[Dict[str, Any], str]] = None
    device_name: Optional[str] = None


class LoginOptionsRequestSchema(BaseModel):
    identifier: str


class LoginVerifyRequestSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    identifier: str
    credential: Optional[Union[Dict[str, Any], str]] = None
