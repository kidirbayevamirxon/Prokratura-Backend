from typing import Optional
from pydantic import BaseModel
from db.models.user import UserRole


class RegisterSchema(BaseModel):
    first_name: str
    last_name: str
    phone: str
    login: Optional[str] = None
    password: str
    role: Optional[UserRole] = UserRole.PROKUROR

