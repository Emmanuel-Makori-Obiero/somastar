"""Upload validation: size cap and real content-type detection by magic bytes
(the client-declared Content-Type and filename are never trusted)."""
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from app.core.errors import api_error

MAGIC = (
    ("application/pdf", b"%PDF-"),
    ("image/png", b"\x89PNG\r\n\x1a\n"),
    ("image/jpeg", b"\xff\xd8\xff"),
)
EXTENSION_FOR = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}
MEDIA_FOR_EXTENSION = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def media_type_for_reference(file_reference: str) -> Optional[str]:
    return MEDIA_FOR_EXTENSION.get(Path(file_reference).suffix.lower())


async def read_validated_upload(file: UploadFile, max_bytes: int) -> tuple[bytes, str]:
    """Returns (content, media_type) or raises a 400/413/415 API error."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise api_error(413, "FILE_TOO_LARGE", f"File is too large. The limit is {max_bytes // (1024 * 1024)} MB.")
        chunks.append(chunk)

    content = b"".join(chunks)
    if not content:
        raise api_error(400, "EMPTY_FILE", "The uploaded file is empty.")

    for media_type, magic in MAGIC:
        if content.startswith(magic):
            return content, media_type
    raise api_error(415, "UNSUPPORTED_FILE_TYPE", "Unsupported file type. Upload a PDF, PNG or JPG.")
