"""Uniform API error shape (CLAUDE.md 31): {"error": {"code", "message", "details"}}."""
from typing import Any, Optional

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str, details: Optional[Any] = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details}},
    )
