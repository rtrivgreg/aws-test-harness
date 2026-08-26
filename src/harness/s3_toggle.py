"""
S3 state toggles.

The harness keeps a single test bucket and flips the attributes that
common S3 managed rules inspect.  Each public function is deliberately
small and named after the compliance intent so the test code stays readable.

Strategies can later be registered in a dict and selected from the
catalog's ``toggle_strategy`` field.
"""

from __future__ import annotations

from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import dry_run_guard, is_dry_run, log


class S3Toggle:
    def __init__(self, bucket_name: str, region: Optional[str] = None):
        self.bucket_name = bucket_name
        self.region = region or "us-east-1"
        self.s3 = boto3.client("s3", region_name=self.region)

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------
    @dry_run_guard("Enable S3 versioning")
    def make_versioning_compliant(self) -> None:
        log(f"Enabling versioning on {self.bucket_name}")
        self.s3.put_bucket_versioning(
            Bucket=self.bucket_name,
            VersioningConfiguration={"Status": "Enabled"},
        )

    @dry_run_guard("Suspend S3 versioning")
    def make_versioning_noncompliant(self) -> None:
        log(f"Suspending versioning on {self.bucket_name}")
        self.s3.put_bucket_versioning(
            Bucket=self.bucket_name,
            VersioningConfiguration={"Status": "Suspended"},
        )

    # ------------------------------------------------------------------
    # Public access block
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Server-side encryption
    # ------------------------------------------------------------------
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

    @dry_run_guard("Remove S3 encryption configuration")
    def make_encryption_noncompliant(self) -> None:
        """
        Note: some accounts have account-level encryption defaults that
        prevent a true “no encryption” state.  In that case the rule may
        still report COMPLIANT; the test should document the limitation.
        """
        log(f"Deleting bucket encryption configuration on {self.bucket_name}")
        try:
            self.s3.delete_bucket_encryption(Bucket=self.bucket_name)
        except ClientError as exc:
            if "ServerSideEncryptionConfigurationNotFoundError" in str(exc):
                log("Encryption config already absent")
            else:
                raise

    # ------------------------------------------------------------------
    # Generic helper used when the catalog only knows the resource type
    # ------------------------------------------------------------------
    def apply_strategy(self, strategy: str, compliant: bool) -> None:
        """
        Dispatch to a concrete toggle based on a strategy name stored in
        the catalog.  Extend this map as more S3 rules are onboarded.
        """
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
            # fallback – try the most common attribute
            "s3_generic": (
                self.make_versioning_compliant
                if compliant
                else self.make_versioning_noncompliant
            ),
        }
        fn = mapping.get(strategy, mapping["s3_generic"])
        fn()
