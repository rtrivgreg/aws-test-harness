"""Throwaway S3 Express directory bucket + lifecycle toggle.

Control-plane APIs use the regional s3express-control endpoint with
path-style addressing. Virtual-hosted CreateSession URLs fail from this VPC.
No Terraform. Always delete the bucket in cleanup.
"""

from __future__ import annotations

from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from harness.dry_run import is_dry_run, log

AZ_CANDIDATES = ("use1-az4", "use1-az5", "use1-az6")
EXPIRATION_DAYS = 7


class S3ExpressLifecycleHarness:
    def __init__(self, test_run_id: str, region: str = "us-east-1") -> None:
        self.test_run_id = test_run_id
        self.region = region
        self.bucket_name: Optional[str] = None
        self.az_id: Optional[str] = None
        self._s3 = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=f"https://s3express-control.{region}.amazonaws.com",
            config=Config(
                s3={"addressing_style": "path", "use_accelerate_endpoint": False},
                retries={"max_attempts": 4, "mode": "standard"},
            ),
        )

    def create(self) -> str:
        if is_dry_run():
            self.bucket_name = f"cfg{self.test_run_id}--use1-az4--x-s3"
            log(f"Dry-run – would create directory bucket {self.bucket_name}")
            return self.bucket_name

        last_exc: Optional[Exception] = None
        for az in AZ_CANDIDATES:
            name = f"cfg{self.test_run_id}--{az}--x-s3"
            try:
                self._s3.create_bucket(
                    Bucket=name,
                    CreateBucketConfiguration={
                        "Location": {"Type": "AvailabilityZone", "Name": az},
                        "Bucket": {
                            "Type": "Directory",
                            "DataRedundancy": "SingleAvailabilityZone",
                        },
                    },
                )
                self.bucket_name = name
                self.az_id = az
                log(f"Created directory bucket {name}")
                return name
            except (ClientError, BotoCoreError) as exc:
                last_exc = exc
                code = ""
                if isinstance(exc, ClientError):
                    code = exc.response.get("Error", {}).get("Code", "")
                log(f"create_bucket {name} failed ({code or type(exc).__name__}); trying next AZ")
        raise RuntimeError(f"Could not create S3 Express directory bucket: {last_exc}")

    def put_expiration(self, days: int = EXPIRATION_DAYS) -> None:
        if not self.bucket_name:
            raise RuntimeError("create() first")
        if is_dry_run():
            log(f"Dry-run – would put lifecycle ExpirationInDays={days} on {self.bucket_name}")
            return
        self._s3.put_bucket_lifecycle_configuration(
            Bucket=self.bucket_name,
            LifecycleConfiguration={
                "Rules": [
                    {
                        "ID": f"harness-{self.test_run_id}",
                        "Status": "Enabled",
                        "Filter": {"Prefix": ""},
                        "Expiration": {"Days": days},
                    }
                ]
            },
        )
        log(f"Lifecycle ExpirationInDays={days} on {self.bucket_name}")

    def delete_lifecycle(self) -> None:
        if not self.bucket_name or is_dry_run():
            return
        try:
            self._s3.delete_bucket_lifecycle(Bucket=self.bucket_name)
            log(f"Deleted lifecycle on {self.bucket_name}")
        except ClientError as exc:
            log(f"delete_bucket_lifecycle ignored: {exc}", style="yellow")

    def cleanup(self) -> None:
        if not self.bucket_name or is_dry_run():
            return
        try:
            self.delete_lifecycle()
        except Exception:
            pass
        try:
            self._s3.delete_bucket(Bucket=self.bucket_name)
            log(f"Deleted directory bucket {self.bucket_name}")
        except ClientError as exc:
            log(f"delete_bucket ignored: {exc}", style="yellow")
