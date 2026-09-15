import os
import uuid
from datetime import datetime
from fastapi import UploadFile, HTTPException, status

PHOTO_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
PDF_MAX_BYTES = 10 * 1024 * 1024    # 10 MB
ICON_MAX_BYTES = 2 * 1024 * 1024   # 2 MB

ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_ICON_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".svg"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}

BASE_UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")


async def save_uploaded_photo(file: UploadFile) -> str:
    """Validate and save photo file to uploads/photos/{YYYY}/{MM}/{DD}/{uuid}.{ext}
    Max size: 5 MB.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photo file must have a filename",
        )

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid photo format. Allowed extensions: {', '.join(ALLOWED_PHOTO_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > PHOTO_MAX_BYTES:
        raise HTTPException(
            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE),
            detail=f"Photo size exceeds maximum allowed limit of 5 MB (received {len(content) / (1024 * 1024):.1f} MB)",
        )

    now = datetime.now()
    year_str = now.strftime("%Y")
    month_str = now.strftime("%m")
    day_str = now.strftime("%d")

    rel_dir = os.path.join("uploads", "photos", year_str, month_str, day_str)
    abs_dir = os.path.join(os.getcwd(), rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(abs_dir, filename)

    with open(file_path, "wb") as f:
        f.write(content)

    return f"/{rel_dir}/{filename}"


async def save_uploaded_icon(file: UploadFile) -> str:
    """Validate and save icon/image file for doc type to uploads/icons/{YYYY}/{MM}/{DD}/{uuid}.{ext}
    Max size: 2 MB.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Icon file must have a filename",
        )

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_ICON_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid icon format. Allowed extensions: {', '.join(ALLOWED_ICON_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > ICON_MAX_BYTES:
        raise HTTPException(
            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE),
            detail=f"Icon size exceeds maximum allowed limit of 2 MB (received {len(content) / (1024 * 1024):.1f} MB)",
        )

    now = datetime.now()
    year_str = now.strftime("%Y")
    month_str = now.strftime("%m")
    day_str = now.strftime("%d")

    rel_dir = os.path.join("uploads", "icons", year_str, month_str, day_str)
    abs_dir = os.path.join(os.getcwd(), rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(abs_dir, filename)

    with open(file_path, "wb") as f:
        f.write(content)

    return f"/{rel_dir}/{filename}"


async def save_uploaded_pdf(file: UploadFile) -> str:
    """Validate and save PDF file to uploads/documents/{YYYY}/{MM}/{DD}/{uuid}.{ext}
    Max size: 10 MB.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document file must have a filename",
        )

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_PDF_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document format. Only PDF files are allowed",
        )

    content = await file.read()
    if len(content) > PDF_MAX_BYTES:
        raise HTTPException(
            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE),
            detail=f"PDF document size exceeds maximum allowed limit of 10 MB (received {len(content) / (1024 * 1024):.1f} MB)",
        )

    now = datetime.now()
    year_str = now.strftime("%Y")
    month_str = now.strftime("%m")
    day_str = now.strftime("%d")

    rel_dir = os.path.join("uploads", "documents", year_str, month_str, day_str)
    abs_dir = os.path.join(os.getcwd(), rel_dir)
    os.makedirs(abs_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(abs_dir, filename)

    with open(file_path, "wb") as f:
        f.write(content)

    return f"/{rel_dir}/{filename}"
