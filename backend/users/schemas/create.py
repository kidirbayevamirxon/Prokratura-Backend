from typing import Optional
from pydantic import BaseModel, Field, model_validator
from db.models.user import UserRole, MAHALLA_SEVEN_ROLES


class UserCreateSchema(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=7, max_length=20)
    login: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=6, description="Optional: can be left empty for future e-imzo/myid auth")
    role: UserRole
    mahalla_id: Optional[int] = None
    photo_url: Optional[str] = None
    birth_date_text: Optional[str] = None
    appointed_date_text: Optional[str] = None
    specialization: Optional[str] = None
    previous_workplace: Optional[str] = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_role_and_mahalla(self):
        if self.role in MAHALLA_SEVEN_ROLES:
            if not self.mahalla_id:
                raise ValueError(
                    f"mahalla_id is required when creating an official with role '{self.role.value}'"
                )
        elif self.role in (UserRole.PROKUROR, UserRole.ADMIN):
            if self.mahalla_id is not None:
                raise ValueError(
                    f"mahalla_id cannot be assigned to '{self.role.value}'"
                )
        return self
