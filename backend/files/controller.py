import mimetypes
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, status, HTTPException
from fastapi.responses import FileResponse

from backend.auth.service import all_guard, prokuror_or_admin_guard, UserAuth
from backend.files.schemas.post import FileUploadResponseSchema
from backend.files.service import FileService

router = APIRouter(prefix="/files", tags=["Files"])


@router.post(
    "/upload",
    response_model=FileUploadResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file (Photo, PDF document, or Icon)",
)
@router.post(
    "",
    response_model=FileUploadResponseSchema,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def upload_file(
    file: UploadFile = File(..., description="File to upload"),
    category: Optional[str] = Form(
        "general",
        description="Category: photos (max 5MB), icons (max 2MB), documents (max 10MB), or general",
    ),
    current_user: UserAuth = Depends(all_guard),
):
    return await FileService.upload_file(file=file, category=category)


@router.get(
    "/{file_path:path}",
    summary="Retrieve and stream a stored file (Photo, PDF, or Icon)",
)
async def get_file(file_path: str):
    abs_path = FileService.get_file_for_serving(file_path)

    # Determine MIME media type
    media_type, _ = mimetypes.guess_type(str(abs_path))
    if not media_type:
        media_type = "application/octet-stream"

    return FileResponse(
        path=str(abs_path),
        media_type=media_type,
        filename=abs_path.name,
    )


@router.delete(
    "/{file_path:path}",
    status_code=status.HTTP_200_OK,
    summary="Delete a stored file from disk (Admin or Prokuror)",
    dependencies=[Depends(prokuror_or_admin_guard)],
)
async def delete_file(file_path: str):
    deleted = FileService.delete_file_by_url_or_path(file_path)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found or already deleted",
        )
    return {"detail": "File deleted successfully", "file_path": file_path}

