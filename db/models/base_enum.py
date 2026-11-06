from typing import Type
from enum import Enum
from sqlalchemy import TypeDecorator, String

class RobustEnumType(TypeDecorator):
    """
    Case-insensitive, robust SQLAlchemy Enum type that accepts both:
    - Member names (e.g. 'PROKUROR', 'ADMIN', 'ACTIVE', 'PENDING')
    - Member values (e.g. 'prokuror', 'admin', 'active', 'pending')
    Prevents SQLAlchemy LookupError when the DB stores enum values in differing cases.
    """
    impl = String(50)
    cache_ok = True

    def __init__(self, enum_cls: Type[Enum], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enum_cls = enum_cls

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, self.enum_cls):
            return value.name
        val_str = str(value).strip().upper()
        if val_str in self.enum_cls.__members__:
            return val_str
        for member in self.enum_cls:
            if member.value.lower() == str(value).strip().lower():
                return member.name
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, self.enum_cls):
            return value
        val_str = str(value).strip()
        val_upper = val_str.upper()
        if val_upper in self.enum_cls.__members__:
            return self.enum_cls[val_upper]
        val_lower = val_str.lower()
        for member in self.enum_cls:
            if member.value.lower() == val_lower:
                return member
        return next(iter(self.enum_cls))

