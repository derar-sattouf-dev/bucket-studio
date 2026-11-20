"""In-memory stand-ins for external services used by the tests."""

from __future__ import annotations

import io
from typing import Any

from botocore.exceptions import ClientError


def _not_found(operation: str) -> ClientError:
    return ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, operation)


class _Paginator:
    def __init__(self, store: FakeS3) -> None:
        self._store = store

    def paginate(self, Bucket: str, Prefix: str = "") -> list[dict[str, Any]]:
        contents = [
            {"Key": key, "Size": len(obj["Body"])}
            for key, obj in sorted(self._store.objects.items())
            if key.startswith(Prefix)
        ]
        return [{"Contents": contents}]


class FakeS3:
    """The subset of the boto3 S3 client API the app uses, backed by a dict."""

    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str, **extra: Any) -> None:
        self.objects[Key] = {"Body": bytes(Body), "ContentType": ContentType, **extra}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise _not_found("GetObject")
        return {"Body": io.BytesIO(self.objects[Key]["Body"])}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise _not_found("HeadObject")
        return {"ContentLength": len(self.objects[Key]["Body"])}

    def copy_object(self, *, Bucket: str, CopySource: dict[str, str], Key: str, **extra: Any) -> None:
        source = self.objects.get(CopySource["Key"])
        if source is None:
            raise _not_found("CopyObject")
        self.objects[Key] = {**{k: v for k, v in source.items() if k != "ACL"}, **extra}

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.objects.pop(Key, None)

    def get_paginator(self, operation: str) -> _Paginator:
        assert operation == "list_objects_v2"
        return _Paginator(self)

    def generate_presigned_url(self, operation: str, Params: dict[str, str], ExpiresIn: int) -> str:
        return f"https://fake-s3.test/{Params['Bucket']}/{Params['Key']}?X-Amz-Expires={ExpiresIn}"

    def body(self, key: str) -> bytes:
        return self.objects[key]["Body"]
