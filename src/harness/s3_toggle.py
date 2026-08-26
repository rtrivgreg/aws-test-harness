"""
S3 state toggles.

The harness keeps a single test bucket and flips the attributes that
common S3 managed rules inspect. After each toggle we also update a
harness-owned tag so AWS Config is more likely to emit a fresh
configuration item promptly.
"""

from __future__ import annotations

import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import dry_run_guard, log


class S3Toggle:
    def __init__(self, bucket_name: str, region: Optional[str] = None):
        self.bucket_name = bucket_name
        self.region = region or "us-east-1"
        self.s3 = boto3.client("s3", region_name=self.region)

    def _nudge_config_recording(self, reason: str) -> None:
        """
        Tag update that gives Config a change it tends to record quickly.
        Does not affect compliance of the versioning/encryption rules under test.
        """
        if True:  # always attempt; dry_run_guard on callers still blocks AWS when dry-run
            pass
        try:
            log(f"Nudging Config via tag update on {self.bucket_name} ({reason})")
            self.s3.put_bucket_tagging(
                Bucket=self.bucket_name,
                Tagging={
                    "TagSet": [
                        {"Key": "Purpose", "Value": "aws-config-rule-testing"},
                        {"Key": "ManagedBy", "Value": "aws-config-test-harness"},
                        {"Key": "harness-last-toggle", "Value": reason},
                        {"Key": "harness-toggle-ts", "Value": str(int(time.time()))},
                    ]
                },
            )
        except ClientError as exc:
            log(f"Tag nudge failed (ignored): {exc}", style="yellow")

    @dry_run_guard("Enable S3 versioning")
    def make_versioning_compliant(self) -> None:
        log(f"Enabling versioning on {self.bucket_name}")
        self.s3.put_bucket_versioning(
            Bucket=self.bucket_name,
            VersioningConfiguration={"Status": "Enabled"},
        )
        self._nudge_config_recording("versioning-enabled")

    @dry_run_guard("Suspend S3 versioning")
    def make_versioning_noncompliant(self) -> None:
        log(f"Suspending versioning on {self.bucket_name}")
        self.s3.put_bucket_versioning(
            Bucket=self.bucket_name,
            VersioningConfiguration={"Status": "Suspended"},
        )
        self._nudge_config_recording("versioning-suspended")

    @dry_run_guard("Lock down S3 public access block")
    def make_public_access_compliant(self) -> None:
        log(f"Enabling full public access block on {self.bucket_name}")
        self.s3.put_public_access_block(
            Bucket=self.bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        self._nudge_config_recording("public-access-locked")

    @dry_run_guard("Relax S3 public access block")
    def make_public_access_noncompliant(self) -> None:
        log(f"Disabling public access block on {self.bucket_name}")
        self.s3.put_public_access_block(
            Bucket=self.bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )
        self._nudge_config_recording("public-access-relaxed")

    @dry_run_guard("Enable S3 SSE-S3")
    def make_encryption_compliant(self) -> None:
        log(f"Enabling AES256 encryption on {self.bucket_name}")
        self.s3.put_bucket_encryption(
            Bucket=self.bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }
                ]
            },
        )
        self._nudge_config_recording("encryption-enabled")

    @dry_run_guard("Remove S3 encryption configuration")
    def make_encryption_noncompliant(self) -> None:
        log(f"Deleting bucket encryption configuration on {self.bucket_name}")
        try:
            self.s3.delete_bucket_encryption(Bucket=self.bucket_name)
        except ClientError as exc:
            if "ServerSideEncryptionConfigurationNotFoundError" in str(exc):
                log("Encryption config already absent")
            else:
                raise
        self._nudge_config_recording("encryption-removed")

    def apply_strategy(self, strategy: str, compliant: bool) -> None:
        mapping = {
            "s3_versioning": (
                self.make_versioning_compliant
                if compliant
                else self.make_versioning_noncompliant
            ),
            "s3_public_access": (
                self.make_public_access_compliant
                if compliant
                else self.make_public_access_noncompliant
            ),
            "s3_encryption": (
                self.make_encryption_compliant
                if compliant
                else self.make_encryption_noncompliant
            ),
            "s3_generic": (
                self.make_versioning_compliant
                if compliant
                else self.make_versioning_noncompliant
            ),
        }
        fn = mapping.get(strategy, mapping["s3_generic"])
        fn()
