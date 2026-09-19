"""Object-storage abstraction (CLAUDE.md 1). Swap LocalStorage for an
S3/GCS-backed implementation in production without touching callers."""
from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def save(self, filename: str, content: bytes) -> str:
        """Persist file content, return a file_reference string."""

    @abstractmethod
    def read(self, file_reference: str) -> bytes:
        """Return raw bytes for a stored file."""

    @abstractmethod
    def delete(self, file_reference: str) -> None:
        """Remove a stored file. Missing files are ignored."""
