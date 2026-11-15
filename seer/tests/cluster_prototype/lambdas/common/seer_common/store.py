"""S3 access for raw records, run manifests, scrape state and the static site."""

import gzip
import json
import os
import tempfile
import threading
from datetime import date, datetime
from typing import Any, Iterator

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

RAW_BUCKET = os.environ.get("RAW_BUCKET", "seer-raw")
SITE_BUCKET = os.environ.get("SITE_BUCKET", "seer-site")
RAW_STORAGE_CLASS = os.environ.get("RAW_STORAGE_CLASS", "INTELLIGENT_TIERING")

_client: Any = None
_ready: set[str] = set()


def client() -> Any:
    global _client
    if _client is None:
        endpoint = os.environ.get("S3_ENDPOINT_URL") or None
        cfg = Config(
            retries={"max_attempts": 5, "mode": "standard"}, s3={"addressing_style": "path" if endpoint else "auto"}
        )
        _client = boto3.client("s3", endpoint_url=endpoint, config=cfg)
    return _client


def ensure_bucket(bucket: str) -> None:
    """Create the bucket when S3_AUTO_CREATE=true (local emulator only; AWS buckets come from IaC)."""
    if bucket in _ready or os.environ.get("S3_AUTO_CREATE", "").lower() != "true":
        return
    try:
        client().head_bucket(Bucket=bucket)
    except ClientError:
        region = client().meta.region_name
        extra = {} if region == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": region}}
        client().create_bucket(Bucket=bucket, **extra)
    _ready.add(bucket)


def _default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=_default, separators=(",", ":"))


def put_bytes(bucket: str, key: str, body: bytes, content_type: str, **extra: Any) -> int:
    ensure_bucket(bucket)
    client().put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type, **extra)
    return len(body)


def get_bytes(bucket: str, key: str) -> bytes | None:
    ensure_bucket(bucket)
    try:
        return client().get_object(Bucket=bucket, Key=key)["Body"].read()
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return None
        raise


def put_json(bucket: str, key: str, obj: Any, gz: bool = False) -> int:
    data = dumps(obj).encode()
    if gz:
        return put_bytes(bucket, key, gzip.compress(data, 6), "application/gzip")
    return put_bytes(bucket, key, data, "application/json")


def get_json(bucket: str, key: str, gz: bool = False) -> Any | None:
    data = get_bytes(bucket, key)
    if data is None:
        return None
    return json.loads(gzip.decompress(data) if gz else data)


class JsonlGzWriter:
    """Thread-safe gzipped JSON-lines writer that spills to /tmp, so raw pages never pile up in memory."""

    def __init__(self) -> None:
        self._file = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024)
        self._gz = gzip.GzipFile(fileobj=self._file, mode="wb", compresslevel=6)
        self._lock = threading.Lock()
        self.count = 0
        self.bytes_raw = 0

    def add(self, record: dict[str, Any]) -> None:
        line = (dumps(record) + "\n").encode()
        with self._lock:
            self._gz.write(line)
            self.count += 1
            self.bytes_raw += len(line)

    def upload(self, bucket: str, key: str) -> tuple[int, int, int]:
        """Upload in the raw storage class. Returns (records, raw bytes, gzip bytes)."""
        self._gz.close()
        size = self._file.tell()
        self._file.seek(0)
        ensure_bucket(bucket)
        client().put_object(
            Bucket=bucket, Key=key, Body=self._file, ContentType="application/gzip", StorageClass=RAW_STORAGE_CLASS
        )
        self._file.close()
        return self.count, self.bytes_raw, size


def iter_jsonl_gz(bucket: str, key: str) -> Iterator[dict[str, Any]]:
    """Stream records one line at a time from S3."""
    ensure_bucket(bucket)
    try:
        body = client().get_object(Bucket=bucket, Key=key)["Body"]
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            raise FileNotFoundError(f"s3://{bucket}/{key}") from e
        raise
    with gzip.GzipFile(fileobj=body) as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def run_id_for(started: datetime, edition: str) -> str:
    return f"{started:%Y%m%dT%H%M%SZ}-{edition}"


def raw_key(edition: str, started: datetime, run_id: str) -> str:
    return f"raw/{edition}/{started:%Y/%m/%d/%H}/{run_id}.jsonl.gz"


def manifest_key(edition: str, run_id: str) -> str:
    return f"runs/{edition}/{run_id}.json"


def state_key(edition: str) -> str:
    return f"state/{edition}.json.gz"
