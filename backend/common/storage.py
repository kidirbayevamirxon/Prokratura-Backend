from fastapi import UploadFile
from backend.files.service import (
    FileService,
    PHOTO_MAX_BYTES,
    PDF_MAX_BYTES,
    ICON_MAX_BYTES,
    ALLOWED_PHOTO_EXTENSIONS,
    ALLOWED_ICON_EXTENSIONS,
    ALLOWED_PDF_EXTENSIONS,
    BASE_STORAGE_DIR as BASE_UPLOAD_DIR,
)


async def save_uploaded_photo(file: UploadFile) -> str:
    """Delegate to FileService.save_uploaded_photo."""
    return await FileService.save_uploaded_photo(file)


async def save_uploaded_icon(file: UploadFile) -> str:
    """Delegate to FileService.save_uploaded_icon."""
    return await FileService.save_uploaded_icon(file)


async def save_uploaded_pdf(file: UploadFile) -> str:
    """Delegate to FileService.save_uploaded_pdf."""
    return await FileService.save_uploaded_pdf(file)


def delete_file_by_url(url_or_path: str) -> bool:
    """Delegate to FileService.delete_file_by_url_or_path."""
    return FileService.delete_file_by_url_or_path(url_or_path)


__all__ = [
    "save_uploaded_photo",
    "save_uploaded_icon",
    "save_uploaded_pdf",
    "delete_file_by_url",
    "PHOTO_MAX_BYTES",
    "PDF_MAX_BYTES",
    "ICON_MAX_BYTES",
    "ALLOWED_PHOTO_EXTENSIONS",
    "ALLOWED_ICON_EXTENSIONS",
    "ALLOWED_PDF_EXTENSIONS",
    "BASE_UPLOAD_DIR",
]
