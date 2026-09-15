from pydantic import BaseModel


class LoginSchema(BaseModel):
    login: str  # Can be login or phone
    password: str

