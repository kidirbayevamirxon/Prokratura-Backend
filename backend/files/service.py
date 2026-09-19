import os
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, HTTPException, status

from backend.files.schemas.post import FileUploadResponseSchema

logger = logging.getLogger(__name__)

PHOTO_MAX_BYTES = 5 * 1024 * 1024   # 5 MB
PDF_MAX_BYTES = 10 * 1024 * 1024     # 10 MB
ICON_MAX_BYTES = 2 * 1024 * 1024    # 2 MB
GENERAL_MAX_BYTES = 10 * 1024 * 1024 # 10 MB

ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_ICON_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".svg"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_GENERAL_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx"
}

BASE_STORAGE_DIR = os.getenv("UPLOAD_DIR", "uploads")


class FileService:
    @classmethod
    def get_base_dir(cls) -> Path:
        base = Path(os.getcwd()) / BASE_STORAGE_DIR
        base.mkdir(parents=True, exist_ok=True)
        return base.resolve()

    @classmethod
    def resolve_safe_path(cls, rel_path: str) -> Path:
        """Resolve a relative or url path safely within the base storage directory.
        Prevents directory traversal attacks (e.g. '../').
        Strips leading prefixes like /files/ or /uploads/.
        """
        clean_rel = rel_path.strip().lstrip("/")
        if clean_rel.startswith("files/"):
            clean_rel = clean_rel[len("files/"):]
        elif clean_rel.startswith("uploads/"):
            clean_rel = clean_rel[len("uploads/"):]

        base = cls.get_base_dir()
        target = (base / clean_rel).resolve()

        # Strict security check: target must be inside base directory
        if not str(target).startswith(str(base)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path (path traversal prohibited)",
            )
        return target

    @classmethod
    def get_file_for_serving(cls, file_path: str) -> Path:
        """Validate and return the Path object of an existing file for streaming.
        Raises 404 if file does not exist.
        """
        target = cls.resolve_safe_path(file_path)
        if not target.exists() or not target.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )
        return target

    @classmethod
    def delete_file_by_url_or_path(cls, url_or_path: Optional[str]) -> bool:
        """Safely delete a physical file from disk using its stored URL or relative path.
        Returns True if deleted, False if file did not exist or path was empty.
        Does not raise exceptions to ensure database transactions are not disrupted.
        """
        if not url_or_path:
            return False
        try:
            target = cls.resolve_safe_path(url_or_path)
            if target.exists() and target.is_file():
                target.unlink()
                logger.info(f"Successfully deleted physical file: {target}")
                return True
        except Exception as e:
            logger.warning(f"Failed to delete file '{url_or_path}': {e}")
        return False

    @classmethod
    async def _write_uploaded_file(
        cls,
        file: UploadFile,
        sub_folder: str,
        allowed_extensions: set[str],
        max_bytes: int,
    ) -> tuple[str, str, int, str]:
        """Validate extension, size, and save file locally on disk.
        Returns (file_url, relative_path, size_bytes, filename).
        """
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must have a filename",
            )

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file format. Allowed extensions: {', '.join(sorted(allowed_extensions))}",
            )

        content = await file.read()
        file_size = len(content)
        if file_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File size exceeds maximum allowed limit of {max_bytes / (1024 * 1024):.1f} MB (received {file_size / (1024 * 1024):.1f} MB)",
            )

        now = datetime.now()
        year_str = now.strftime("%Y")
        month_str = now.strftime("%m")
        day_str = now.strftime("%d")

        rel_dir = os.path.join(sub_folder, year_str, month_str, day_str)
        abs_dir = cls.get_base_dir() / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid.uuid4().hex}{ext}"
        abs_file_path = abs_dir / filename

        with open(abs_file_path, "wb") as f:
            f.write(content)

        relative_path = f"{rel_dir}/{filename}"
        file_url = f"/files/{relative_path}"
        return file_url, relative_path, file_size, filename

    @classmethod
    async def save_uploaded_photo(cls, file: UploadFile) -> str:
        """Validate and save photo file to photos/{YYYY}/{MM}/{DD}/{uuid}.{ext}
        Max size: 5 MB. Returns /files/photos/...
        """
        file_url, _, _, _ = await cls._write_uploaded_file(
            file=file,
            sub_folder="photos",
            allowed_extensions=ALLOWED_PHOTO_EXTENSIONS,
            max_bytes=PHOTO_MAX_BYTES,
        )
        return file_url

    @classmethod
    async def save_uploaded_icon(cls, file: UploadFile) -> str:
        """Validate and save icon file to icons/{YYYY}/{MM}/{DD}/{uuid}.{ext}
        Max size: 2 MB. Returns /files/icons/...
        """
        file_url, _, _, _ = await cls._write_uploaded_file(
            file=file,
            sub_folder="icons",
            allowed_extensions=ALLOWED_ICON_EXTENSIONS,
            max_bytes=ICON_MAX_BYTES,
        )
        return file_url

    @classmethod
    async def save_uploaded_pdf(cls, file: UploadFile) -> str:
        """Validate and save PDF file to documents/{YYYY}/{MM}/{DD}/{uuid}.{ext}
        Max size: 10 MB. Returns /files/documents/...
        """
        file_url, _, _, _ = await cls._write_uploaded_file(
            file=file,
            sub_folder="documents",
            allowed_extensions=ALLOWED_PDF_EXTENSIONS,
            max_bytes=PDF_MAX_BYTES,
        )
        return file_url

    @classmethod
    async def upload_file(
        cls,
        file: UploadFile,
        category: Optional[str] = "general",
    ) -> FileUploadResponseSchema:
        """Generic file upload handler for the dedicated POST /files/upload route."""
        cat = (category or "general").lower().strip()
        if cat == "photos":
            allowed = ALLOWED_PHOTO_EXTENSIONS
            limit = PHOTO_MAX_BYTES
            folder = "photos"
        elif cat == "icons":
            allowed = ALLOWED_ICON_EXTENSIONS
            limit = ICON_MAX_BYTES
            folder = "icons"
        elif cat == "documents":
            allowed = ALLOWED_PDF_EXTENSIONS
            limit = PDF_MAX_BYTES
            folder = "documents"
        else:
            allowed = ALLOWED_GENERAL_EXTENSIONS
            limit = GENERAL_MAX_BYTES
            folder = "general"

        file_url, relative_path, file_size, filename = await cls._write_uploaded_file(
            file=file,
            sub_folder=folder,
            allowed_extensions=allowed,
            max_bytes=limit,
        )

        return FileUploadResponseSchema(
            file_url=file_url,
            relative_path=relative_path,
            filename=filename,
            original_name=file.filename or filename,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=file_size,
        )

