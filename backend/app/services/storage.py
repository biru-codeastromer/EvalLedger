from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO, cast
from uuid import uuid4

import aiofiles
import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.errors import AppError


@dataclass(slots=True)
class StoredArtifact:
    storage_key: str
    artifact_url: str
    size_bytes: int
    sha256: str


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = Path(settings.storage_root)
        self._client: BaseClient | None = None

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> StorageService:
        return cls(settings or get_settings())

    @property
    def client(self) -> BaseClient:
        if self._client is None:
            self._client = cast(
                BaseClient,
                boto3.client(
                    "s3",
                    endpoint_url=self.settings.storage_s3_endpoint_url,
                    aws_access_key_id=self.settings.storage_s3_access_key_id,
                    aws_secret_access_key=self.settings.storage_s3_secret_access_key,
                    region_name=self.settings.storage_s3_region,
                    config=Config(
                        connect_timeout=5,
                        read_timeout=30,
                        retries={"max_attempts": 3, "mode": "standard"},
                    ),
                ),
            )
        return self._client

    async def ensure_ready(self) -> None:
        if self.settings.storage_backend == "local":
            self.root.mkdir(parents=True, exist_ok=True)
            return

        def _ensure_bucket() -> None:
            # Use head_bucket instead of list_buckets: list_buckets requires
            # account-level permission (s3:ListAllMyBuckets) that Cloudflare R2
            # API tokens do not grant by default.  head_bucket only needs
            # bucket-scoped read access and is supported by all S3-compatible
            # providers.
            try:
                self.client.head_bucket(Bucket=self.settings.storage_bucket)
            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code in {"404", "NoSuchBucket"}:
                    # Bucket does not exist.  Try to create it automatically.
                    # This succeeds for AWS S3 and MinIO.
                    # For Cloudflare R2 the bucket must be created in the R2
                    # dashboard first — creation via S3 API is not supported.
                    self.client.create_bucket(Bucket=self.settings.storage_bucket)
                else:
                    raise

        await asyncio.to_thread(_ensure_bucket)

    async def upload_upload_file(
        self,
        filename: str,
        fileobj: BinaryIO,
        *,
        directory: str,
    ) -> StoredArtifact:
        storage_key = f"{directory}/{uuid4().hex}-{filename}"
        fileobj.seek(0)
        if self.settings.storage_backend == "local":
            target_path = self.root / storage_key
            target_path.parent.mkdir(parents=True, exist_ok=True)
            hash_state = sha256()
            size_bytes = 0
            async with aiofiles.open(target_path, "wb") as output:
                while chunk := fileobj.read(1024 * 1024):
                    size_bytes += len(chunk)
                    hash_state.update(chunk)
                    await output.write(chunk)
            return StoredArtifact(
                storage_key=storage_key,
                artifact_url=str(target_path),
                size_bytes=size_bytes,
                sha256=hash_state.hexdigest(),
            )

        def _measure() -> tuple[int, str]:
            hash_state = sha256()
            size_bytes = 0
            fileobj.seek(0)
            while chunk := fileobj.read(1024 * 1024):
                size_bytes += len(chunk)
                hash_state.update(chunk)
            fileobj.seek(0)
            return size_bytes, hash_state.hexdigest()

        size_bytes, digest_hex = await asyncio.to_thread(_measure)

        def _upload() -> None:
            self.client.upload_fileobj(fileobj, self.settings.storage_bucket, storage_key)

        await asyncio.to_thread(_upload)
        return StoredArtifact(
            storage_key=storage_key,
            artifact_url=storage_key,
            size_bytes=size_bytes,
            sha256=digest_hex,
        )

    async def upload_bytes(self, filename: str, data: bytes, *, directory: str) -> StoredArtifact:
        storage_key = f"{directory}/{uuid4().hex}-{filename}"
        digest_hex = sha256(data).hexdigest()
        if self.settings.storage_backend == "local":
            target_path = self.root / storage_key
            target_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(target_path, "wb") as output:
                await output.write(data)
            return StoredArtifact(
                storage_key=storage_key,
                artifact_url=str(target_path),
                size_bytes=len(data),
                sha256=digest_hex,
            )

        def _upload() -> None:
            self.client.put_object(Bucket=self.settings.storage_bucket, Key=storage_key, Body=data)

        await asyncio.to_thread(_upload)
        return StoredArtifact(
            storage_key=storage_key,
            artifact_url=storage_key,
            size_bytes=len(data),
            sha256=digest_hex,
        )

    async def read_bytes(self, storage_key_or_url: str) -> bytes:
        if self.settings.storage_backend == "local":
            async with aiofiles.open(storage_key_or_url, "rb") as input_file:
                return cast(bytes, await input_file.read())

        def _read() -> bytes:
            response = self.client.get_object(
                Bucket=self.settings.storage_bucket, Key=storage_key_or_url
            )
            return cast(bytes, response["Body"].read())

        return await asyncio.to_thread(_read)

    async def delete(self, storage_key_or_url: str) -> None:
        if self.settings.storage_backend == "local":
            def _unlink() -> None:
                Path(storage_key_or_url).unlink(missing_ok=True)

            await asyncio.to_thread(_unlink)
            return

        def _delete() -> None:
            try:
                self.client.delete_object(
                    Bucket=self.settings.storage_bucket, Key=storage_key_or_url
                )
            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code in {"404", "NoSuchKey"}:
                    # Object already absent — deletion is idempotent.
                    return
                raise

        await asyncio.to_thread(_delete)

    async def generate_download_url(self, storage_key_or_url: str) -> str:
        if self.settings.storage_backend == "local":
            return storage_key_or_url

        external_endpoint = self.settings.storage_s3_presign_endpoint
        if not external_endpoint:
            raise AppError("storage_error", "Presign endpoint is not configured", status_code=500)

        def _presign() -> str:
            url = cast(
                str,
                self.client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.settings.storage_bucket, "Key": storage_key_or_url},
                    ExpiresIn=self.settings.storage_s3_presign_ttl,
                ),
            )
            if self.settings.storage_s3_endpoint_url:
                return url.replace(self.settings.storage_s3_endpoint_url, external_endpoint)
            return url

        try:
            return await asyncio.to_thread(_presign)
        except ClientError as exc:
            raise AppError("storage_error", "Could not generate download URL", status_code=500) from exc
