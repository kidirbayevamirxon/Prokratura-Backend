import logging
from sqlalchemy import event

from db.models.document import CheckInDocument
from db.models.user import User
from db.models.category import Category

logger = logging.getLogger(__name__)


@event.listens_for(CheckInDocument, "after_delete")
def cleanup_document_files(mapper, connection, target: CheckInDocument):
    """Automatically delete physical photo and PDF files when a CheckInDocument is deleted from DB."""
    from backend.files.service import FileService
    if target.photo_url:
        deleted = FileService.delete_file_by_url_or_path(target.photo_url)
        if deleted:
            logger.info(f"Deleted document photo: {target.photo_url}")
    if target.pdf_url:
        deleted = FileService.delete_file_by_url_or_path(target.pdf_url)
        if deleted:
            logger.info(f"Deleted document PDF: {target.pdf_url}")


@event.listens_for(User, "after_delete")
def cleanup_user_photo(mapper, connection, target: User):
    """Automatically delete physical photo file when a User is deleted from DB."""
    from backend.files.service import FileService
    if target.photo_url:
        deleted = FileService.delete_file_by_url_or_path(target.photo_url)
        if deleted:
            logger.info(f"Deleted user photo: {target.photo_url}")


@event.listens_for(Category, "after_delete")
def cleanup_category_icon(mapper, connection, target: Category):
    """Automatically delete physical icon file when a Category is deleted from DB."""
    from backend.files.service import FileService
    if target.icon_url:
        deleted = FileService.delete_file_by_url_or_path(target.icon_url)
        if deleted:
            logger.info(f"Deleted category icon: {target.icon_url}")

