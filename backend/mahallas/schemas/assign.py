from typing import List, Optional
from pydantic import BaseModel, field_validator
from db.models.user import UserRole, MAHALLA_SEVEN_ROLES


class AssignMemberSchema(BaseModel):
    user_id: int
    role: UserRole

    @field_validator("role")
    @classmethod
    def validate_role_is_mahalla_member(cls, v: UserRole):
        if v not in MAHALLA_SEVEN_ROLES:
            raise ValueError(
                f"Role '{v.value}' is not a valid Mahalla member role. "
                f"Must be one of: {[r.value for r in MAHALLA_SEVEN_ROLES]}"
            )
        return v


class RemoveMemberSchema(BaseModel):
    user_id: int

