from backend.mahallas.schemas.create import MahallaCreateSchema
from backend.mahallas.schemas.patch import MahallaUpdateSchema
from backend.mahallas.schemas.get import (
    MahallaDetailSchema,
    MahallaMemberSimpleSchema,
    PaginatedMahallaSchema,
)

__all__ = [
    "MahallaCreateSchema",
    "MahallaUpdateSchema",
    "MahallaDetailSchema",
    "MahallaMemberSimpleSchema",
    "PaginatedMahallaSchema",
]
