from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import UploadFile

from app.config import Settings
from app.errors import AppError
from app.utils.uploads import validate_upload_file


def test_validate_upload_file_rejects_unsupported_extensions() -> None:
    settings = Settings(allowed_artifact_extensions=[".json", ".jsonl"])
    upload = UploadFile(filename="artifact.exe", file=BytesIO(b"abc"))

    with pytest.raises(AppError) as caught_error:
        validate_upload_file(upload, authenticated=True, settings=settings)

    assert caught_error.value.code == "unsupported_artifact"


def test_validate_upload_file_requires_auth_for_large_public_upload() -> None:
    settings = Settings(max_public_upload_bytes=4, max_authenticated_upload_bytes=100)
    upload = UploadFile(filename="artifact.jsonl", file=BytesIO(b"hello world"))

    with pytest.raises(AppError) as caught_error:
        validate_upload_file(upload, authenticated=False, settings=settings)

    assert caught_error.value.code == "auth_required"
