import uuid
from pathlib import Path

from app.config import get_settings
from app.integrations.storage.base import StorageBackend

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


class LocalStorage(StorageBackend):
    def __init__(self):
        self.root = Path(get_settings().STORAGE_LOCAL_DIR).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, file_reference: str) -> Path:
        # Never trust the reference: resolve and make sure it stays inside root.
        p = (self.root / file_reference).resolve()
        if p.parent != self.root:
            raise ValueError("Invalid file reference.")
        return p

    def save(self, filename: str, content: bytes) -> str:
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            ext = ".bin"
        ref = f"{uuid.uuid4()}{ext}"  # original filename is never used on disk
        self._path(ref).write_bytes(content)
        return ref

    def read(self, file_reference: str) -> bytes:
        return self._path(file_reference).read_bytes()

    def delete(self, file_reference: str) -> None:
        self._path(file_reference).unlink(missing_ok=True)


def get_storage() -> StorageBackend:
    # Only "local" is implemented; production would branch on
    # settings.STORAGE_BACKEND to return an S3/GCS-backed instance.
    return LocalStorage()
