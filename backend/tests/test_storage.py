"""Tests for StorageService.

Covers:
- local backend: upload_upload_file, upload_bytes, read_bytes, generate_download_url
- s3 backend: ensure_ready (bucket exists / bucket not found → creates)
- s3 backend: ensure_ready propagates unexpected ClientError
- s3 backend: upload_upload_file (mocked boto3)
- s3 backend: upload_bytes (mocked boto3)
- s3 backend: read_bytes (mocked boto3)
- s3 backend: generate_download_url (presign with endpoint URL replacement)
- s3 backend: generate_download_url raises AppError when presign endpoint not set
- s3 backend: generate_download_url raises AppError on ClientError
- Settings: STORAGE_BACKEND=s3 with missing credentials raises ValueError
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from app.config import Settings
from app.errors import AppError
from app.services.storage import StorageService, StoredArtifact

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _local_settings(tmp_path) -> Settings:  # type: ignore[no-untyped-def]
    return Settings(
        storage_backend="local",
        storage_root=str(tmp_path / "storage"),
    )


def _s3_settings() -> Settings:
    return Settings(
        storage_backend="s3",
        storage_bucket="test-bucket",
        storage_s3_endpoint_url="https://fake.endpoint",
        storage_s3_access_key_id="fake-key-id",
        storage_s3_secret_access_key="fake-secret",
        storage_s3_presign_endpoint="https://pub.fake.endpoint",
        storage_s3_presign_ttl=300,
    )


def _make_mock_client() -> MagicMock:
    """Return a MagicMock that stands in for the boto3 S3 client."""
    return MagicMock()


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "mock"}}, "HeadBucket")


# ---------------------------------------------------------------------------
# Local backend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_ensure_ready_creates_dir(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = StorageService(_local_settings(tmp_path))
    await svc.ensure_ready()
    assert svc.root.is_dir()


@pytest.mark.asyncio
async def test_local_upload_upload_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = StorageService(_local_settings(tmp_path))
    await svc.ensure_ready()

    data = b"hello world"
    fileobj = BytesIO(data)
    result = await svc.upload_upload_file("test.json", fileobj, directory="benchmarks")

    assert isinstance(result, StoredArtifact)
    assert result.size_bytes == len(data)
    assert result.sha256 == hashlib.sha256(data).hexdigest()
    assert result.storage_key.startswith("benchmarks/")
    assert result.storage_key.endswith("-test.json")
    # artifact_url is an absolute path string pointing at the stored file
    assert result.artifact_url.endswith(result.storage_key)


@pytest.mark.asyncio
async def test_local_upload_bytes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = StorageService(_local_settings(tmp_path))
    await svc.ensure_ready()

    data = b"{"
    result = await svc.upload_bytes("meta.json", data, directory="meta")

    assert result.size_bytes == len(data)
    assert result.sha256 == hashlib.sha256(data).hexdigest()


@pytest.mark.asyncio
async def test_local_read_bytes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = StorageService(_local_settings(tmp_path))
    await svc.ensure_ready()

    data = b"round-trip"
    result = await svc.upload_bytes("round.json", data, directory="rt")
    read_back = await svc.read_bytes(result.artifact_url)

    assert read_back == data


@pytest.mark.asyncio
async def test_local_generate_download_url_returns_path(tmp_path) -> None:  # type: ignore[no-untyped-def]
    svc = StorageService(_local_settings(tmp_path))
    url = await svc.generate_download_url("/some/path/artifact.json")
    assert url == "/some/path/artifact.json"


# ---------------------------------------------------------------------------
# S3 backend — ensure_ready
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s3_ensure_ready_bucket_exists() -> None:
    """head_bucket succeeds → no create_bucket call."""
    svc = StorageService(_s3_settings())
    mock_client = _make_mock_client()
    svc._client = mock_client

    await svc.ensure_ready()

    mock_client.head_bucket.assert_called_once_with(Bucket="test-bucket")
    mock_client.create_bucket.assert_not_called()


@pytest.mark.asyncio
async def test_s3_ensure_ready_bucket_not_found_creates_it() -> None:
    """head_bucket returns 404 → create_bucket is called."""
    svc = StorageService(_s3_settings())
    mock_client = _make_mock_client()
    mock_client.head_bucket.side_effect = _make_client_error("404")
    svc._client = mock_client

    await svc.ensure_ready()

    mock_client.create_bucket.assert_called_once_with(Bucket="test-bucket")


@pytest.mark.asyncio
async def test_s3_ensure_ready_no_such_bucket_creates_it() -> None:
    """head_bucket returns NoSuchBucket → create_bucket is called."""
    svc = StorageService(_s3_settings())
    mock_client = _make_mock_client()
    mock_client.head_bucket.side_effect = _make_client_error("NoSuchBucket")
    svc._client = mock_client

    await svc.ensure_ready()

    mock_client.create_bucket.assert_called_once_with(Bucket="test-bucket")


@pytest.mark.asyncio
async def test_s3_ensure_ready_unexpected_error_propagates() -> None:
    """Unexpected ClientError (e.g. 403 permission denied) should propagate."""
    svc = StorageService(_s3_settings())
    mock_client = _make_mock_client()
    mock_client.head_bucket.side_effect = _make_client_error("403")
    svc._client = mock_client

    with pytest.raises(ClientError):
        await svc.ensure_ready()


# ---------------------------------------------------------------------------
# S3 backend — upload_upload_file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s3_upload_upload_file_returns_storage_key() -> None:
    svc = StorageService(_s3_settings())
    mock_client = _make_mock_client()
    svc._client = mock_client

    data = b"benchmark data"
    fileobj = BytesIO(data)
    result = await svc.upload_upload_file("results.json", fileobj, directory="bmarks")

    assert result.storage_key.startswith("bmarks/")
    assert result.storage_key.endswith("-results.json")
    # artifact_url is the storage key for S3 (not a real URL)
    assert result.artifact_url == result.storage_key
    assert result.size_bytes == len(data)
    assert result.sha256 == hashlib.sha256(data).hexdigest()
    mock_client.upload_fileobj.assert_called_once()


# ---------------------------------------------------------------------------
# S3 backend — upload_bytes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s3_upload_bytes_uses_put_object() -> None:
    svc = StorageService(_s3_settings())
    mock_client = _make_mock_client()
    svc._client = mock_client

    data = b"small payload"
    result = await svc.upload_bytes("meta.json", data, directory="meta")

    assert result.size_bytes == len(data)
    assert result.sha256 == hashlib.sha256(data).hexdigest()
    mock_client.put_object.assert_called_once()
    call_kwargs = mock_client.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "test-bucket"
    assert call_kwargs["Body"] == data


# ---------------------------------------------------------------------------
# S3 backend — read_bytes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s3_read_bytes_returns_body() -> None:
    svc = StorageService(_s3_settings())
    mock_client = _make_mock_client()
    expected = b"stored content"
    mock_client.get_object.return_value = {"Body": BytesIO(expected)}
    # get_object Body.read() is called inside the sync helper
    body_mock = MagicMock()
    body_mock.read.return_value = expected
    mock_client.get_object.return_value = {"Body": body_mock}
    svc._client = mock_client

    result = await svc.read_bytes("some/key.json")

    assert result == expected
    mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="some/key.json")


# ---------------------------------------------------------------------------
# S3 backend — generate_download_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s3_generate_download_url_replaces_endpoint() -> None:
    """Presigned URL has internal endpoint replaced with the public presign endpoint."""
    svc = StorageService(_s3_settings())
    mock_client = _make_mock_client()
    mock_client.generate_presigned_url.return_value = (
        "https://fake.endpoint/test-bucket/mykey?X-Amz-Signature=abc"
    )
    svc._client = mock_client

    url = await svc.generate_download_url("mykey")

    assert url.startswith("https://pub.fake.endpoint/")
    # The internal S3 endpoint must no longer appear in the public URL
    assert "https://fake.endpoint" not in url
    mock_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "test-bucket", "Key": "mykey"},
        ExpiresIn=300,
    )


@pytest.mark.asyncio
async def test_s3_generate_download_url_respects_ttl() -> None:
    """ExpiresIn uses settings.storage_s3_presign_ttl (not a hardcoded value)."""
    settings = _s3_settings()
    settings.storage_s3_presign_ttl = 7200
    svc = StorageService(settings)
    mock_client = _make_mock_client()
    mock_client.generate_presigned_url.return_value = (
        "https://fake.endpoint/test-bucket/k?sig=x"
    )
    svc._client = mock_client

    await svc.generate_download_url("k")

    _, call_kwargs = mock_client.generate_presigned_url.call_args
    assert call_kwargs["ExpiresIn"] == 7200


@pytest.mark.asyncio
async def test_s3_generate_download_url_missing_presign_endpoint_raises() -> None:
    """AppError raised when STORAGE_S3_PRESIGN_ENDPOINT is not set."""
    # Build a valid settings object, then forcibly clear the presign endpoint
    # to simulate a partially-configured environment (bypassing the validator).
    settings = _s3_settings()
    object.__setattr__(settings, "storage_s3_presign_endpoint", None)
    svc = StorageService(settings)
    mock_client = _make_mock_client()
    svc._client = mock_client

    with pytest.raises(AppError) as exc_info:
        await svc.generate_download_url("mykey")

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_s3_generate_download_url_client_error_raises_app_error() -> None:
    """ClientError from generate_presigned_url is wrapped into AppError."""
    svc = StorageService(_s3_settings())
    mock_client = _make_mock_client()
    mock_client.generate_presigned_url.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "not found"}}, "GetObject"
    )
    svc._client = mock_client

    with pytest.raises(AppError) as exc_info:
        await svc.generate_download_url("missing-key")

    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Settings validation
# ---------------------------------------------------------------------------


def test_settings_s3_missing_credentials_raises() -> None:
    """STORAGE_BACKEND=s3 without credentials should raise ValueError at init."""
    with pytest.raises(ValueError, match="STORAGE_BACKEND=s3 requires"):
        Settings(
            storage_backend="s3",
            # credentials intentionally omitted
        )


def test_settings_s3_partial_credentials_raises() -> None:
    """STORAGE_BACKEND=s3 with only some credentials should raise ValueError."""
    with pytest.raises(ValueError, match="STORAGE_BACKEND=s3 requires"):
        Settings(
            storage_backend="s3",
            storage_s3_endpoint_url="https://fake.endpoint",
            storage_s3_access_key_id="key",
            # secret and presign endpoint missing
        )


def test_settings_s3_all_credentials_valid() -> None:
    """STORAGE_BACKEND=s3 with all credentials should not raise."""
    settings = _s3_settings()
    assert settings.storage_backend == "s3"
    assert settings.storage_s3_presign_ttl == 300


def test_settings_local_no_credentials_required() -> None:
    """STORAGE_BACKEND=local should not require any S3 credentials."""
    settings = Settings(storage_backend="local")
    assert settings.storage_backend == "local"
