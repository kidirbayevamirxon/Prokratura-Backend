from db.models.mahalla import Mahalla
from db.models.user import User, UserRole, MAHALLA_SEVEN_ROLES
from db.models.category import Category
from db.models.person import Person
from db.models.assignment import PersonCategoryAssignment, AssignmentStatus
from db.models.document import CheckInDocument, CheckInDocType, CheckInDocStatus
from db.models.document_message import DocumentMessage, DocumentMessageType
from db.models.mahalla_stats import MahallaStats
import db.events  # Register automatic file deletion listeners

__all__ = [
    "Mahalla",
    "MahallaStats",
    "User",
    "UserRole",
    "MAHALLA_SEVEN_ROLES",
    "Category",
    "Person",
    "PersonCategoryAssignment",
    "AssignmentStatus",
    "CheckInDocument",
    "CheckInDocType",
    "CheckInDocStatus",
    "DocumentMessage",
    "DocumentMessageType",
]
