from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from app.config import Settings, get_settings
from app.errors import AppError

_upload_logger = logging.getLogger("evalledger.uploads")


@dataclass(slots=True)
class UploadDescriptor:
    filename: str
    suffix: str
    size_bytes: int


def _measure_size(fileobj: BinaryIO) -> int:
    fileobj.seek(0, 2)
    size_bytes = fileobj.tell()
    fileobj.seek(0)
    return size_bytes


def validate_upload_name(filename: str | None, settings: Settings | None = None) -> str:
    current_settings = settings or get_settings()
    safe_name = Path(filename or "artifact.bin").name.strip()
    if safe_name in {"", ".", ".."}:
        _upload_logger.warning(
            "upload.invalid_filename", extra={"artifact_filename": filename, "reason": "unsafe_name"}
        )
        raise AppError("invalid_filename", "A valid artifact filename is required", status_code=400)
    if len(safe_name) > 255:
        _upload_logger.warning(
            "upload.invalid_filename", extra={"artifact_filename": safe_name[:64], "reason": "name_too_long"}
        )
        raise AppError("invalid_filename", "Artifact filename is too long", status_code=400)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in set(current_settings.allowed_artifact_extensions):
        _upload_logger.warning(
            "upload.unsupported_extension",
            extra={"artifact_filename": safe_name, "suffix": suffix},
        )
        raise AppError(
            "unsupported_artifact",
            "Artifacts must be one of: json, jsonl, csv, or parquet",
            status_code=400,
        )
    return safe_name


def validate_upload_file(
    upload: UploadFile,
    *,
    authenticated: bool,
    settings: Settings | None = None,
) -> UploadDescriptor:
    current_settings = settings or get_settings()
    safe_name = validate_upload_name(upload.filename, current_settings)
    size_bytes = _measure_size(upload.file)
    if size_bytes <= 0:
        _upload_logger.warning(
            "upload.empty_artifact",
            extra={"artifact_filename": safe_name, "size_bytes": size_bytes},
        )
        raise AppError("empty_artifact", "Uploaded artifacts cannot be empty", status_code=400)
    max_bytes = (
        current_settings.max_authenticated_upload_bytes
        if authenticated
        else current_settings.max_public_upload_bytes
    )
    if size_bytes > max_bytes:
        _upload_logger.warning(
            "upload.artifact_too_large",
            extra={
                "artifact_filename": safe_name,
                "size_bytes": size_bytes,
                "max_bytes": max_bytes,
                "authenticated": authenticated,
            },
        )
        if authenticated:
            raise AppError(
                "artifact_too_large",
                f"Authenticated uploads are limited to {max_bytes // (1024 * 1024)}MB",
                status_code=413,
            )
        raise AppError(
            "auth_required",
            f"Authentication is required for uploads larger than {max_bytes // (1024 * 1024)}MB",
            status_code=401,
        )
    return UploadDescriptor(
        filename=safe_name,
        suffix=Path(safe_name).suffix.lower(),
        size_bytes=size_bytes,
    )
