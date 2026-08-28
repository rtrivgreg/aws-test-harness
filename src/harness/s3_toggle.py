"""
S3 state toggles.
"""

from __future__ import annotations

import json
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import dry_run_guard, log

PROOF_TAG_KEY = "HarnessProof"


class S3Toggle:
    def __init__(self, bucket_name: str, region: Optional[str] = None):
        self.bucket_name = bucket_name
        self.region = region or "us-east-1"
        self.s3 = boto3.client("s3", region_name=self.region)

    def _nudge_config_recording(self, reason: str) -> None:
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

    def _put_tags(self, extra: list[dict], reason: str) -> None:
        tags = [
            {"Key": "Purpose", "Value": "aws-config-rule-testing"},
            {"Key": "ManagedBy", "Value": "aws-config-test-harness"},
            {"Key": "harness-last-toggle", "Value": reason[:128]},
            {"Key": "harness-toggle-ts", "Value": str(int(time.time()))},
        ] + extra
        self.s3.put_bucket_tagging(Bucket=self.bucket_name, Tagging={"TagSet": tags})

    def _public_read_policy(self) -> str:
        return json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "HarnessPublicRead",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{self.bucket_name}/*",
            }],
        })

    def _public_write_policy(self) -> str:
        return json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "HarnessPublicWrite",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:PutObject",
                "Resource": f"arn:aws:s3:::{self.bucket_name}/*",
            }],
        })

    def _delete_bucket_policy(self) -> None:
        try:
            self.s3.delete_bucket_policy(Bucket=self.bucket_name)
        except ClientError as exc:
            if "NoSuchBucketPolicy" in str(exc):
                log("Bucket policy already absent")
            else:
                raise

    def _set_ownership(self, setting: str) -> None:
        log(f"Setting object ownership={setting} on {self.bucket_name}")
        self.s3.put_bucket_ownership_controls(
            Bucket=self.bucket_name,
            OwnershipControls={"Rules": [{"ObjectOwnership": setting}]},
        )

    def _put_encryption(self, algorithm: str) -> None:
        log(f"Setting default encryption={algorithm} on {self.bucket_name}")
        self.s3.put_bucket_encryption(
            Bucket=self.bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [{
                    "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": algorithm}
                }]
            },
        )

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

    @dry_run_guard("Put S3 lifecycle configuration")
    def make_lifecycle_compliant(self) -> None:
        log(f"Putting enabled lifecycle rule on {self.bucket_name}")
        self.s3.put_bucket_lifecycle_configuration(
            Bucket=self.bucket_name,
            LifecycleConfiguration={
                "Rules": [{
                    "ID": "harness-lifecycle",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "Expiration": {"Days": 365},
                }]
            },
        )
        self._nudge_config_recording("lifecycle-enabled")

    @dry_run_guard("Delete S3 lifecycle configuration")
    def make_lifecycle_noncompliant(self) -> None:
        log(f"Deleting lifecycle configuration on {self.bucket_name}")
        try:
            self.s3.delete_bucket_lifecycle(Bucket=self.bucket_name)
        except ClientError as exc:
            if "NoSuchLifecycleConfiguration" in str(exc):
                log("Lifecycle configuration already absent")
            else:
                raise
        self._nudge_config_recording("lifecycle-removed")

    @dry_run_guard("Versioning on + lifecycle on")
    def make_version_lifecycle_compliant(self) -> None:
        self.make_versioning_compliant()
        self.make_lifecycle_compliant()

    @dry_run_guard("Versioning on + lifecycle off")
    def make_version_lifecycle_noncompliant(self) -> None:
        self.make_versioning_compliant()
        self.make_lifecycle_noncompliant()

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

    @dry_run_guard("Allow public GetObject + relax BPA")
    def make_public_read_noncompliant(self) -> None:
        self.make_public_access_noncompliant()
        log(f"Putting public GetObject policy on {self.bucket_name}")
        self.s3.put_bucket_policy(
            Bucket=self.bucket_name, Policy=self._public_read_policy()
        )
        self._nudge_config_recording("public-read-policy")

    @dry_run_guard("Remove public policy + lock BPA")
    def make_public_read_compliant(self) -> None:
        log(f"Deleting bucket policy on {self.bucket_name}")
        self._delete_bucket_policy()
        self.make_public_access_compliant()
        self._nudge_config_recording("public-read-removed")

    @dry_run_guard("Allow public PutObject + relax BPA")
    def make_public_write_noncompliant(self) -> None:
        self.make_public_access_noncompliant()
        log(f"Putting public PutObject policy on {self.bucket_name}")
        self.s3.put_bucket_policy(
            Bucket=self.bucket_name, Policy=self._public_write_policy()
        )
        self._nudge_config_recording("public-write-policy")

    @dry_run_guard("Remove public write policy + lock BPA")
    def make_public_write_compliant(self) -> None:
        log(f"Deleting bucket policy on {self.bucket_name}")
        self._delete_bucket_policy()
        self.make_public_access_compliant()
        self._nudge_config_recording("public-write-removed")

    @dry_run_guard("Enable ACLs and grant public-read")
    def make_acl_noncompliant(self) -> None:
        self.make_public_access_noncompliant()
        self._set_ownership("BucketOwnerPreferred")
        log(f"Putting canned public-read ACL on {self.bucket_name}")
        self.s3.put_bucket_acl(Bucket=self.bucket_name, ACL="public-read")
        self._nudge_config_recording("acl-public-read")

    @dry_run_guard("Private ACL + BucketOwnerEnforced")
    def make_acl_compliant(self) -> None:
        try:
            self._set_ownership("BucketOwnerPreferred")
            self.s3.put_bucket_acl(Bucket=self.bucket_name, ACL="private")
        except ClientError as exc:
            log(f"private ACL (ignored): {exc}", style="yellow")
        self._set_ownership("BucketOwnerEnforced")
        self.make_public_access_compliant()
        self._nudge_config_recording("acls-disabled")

    @dry_run_guard("Enable S3 SSE-S3")
    def make_encryption_compliant(self) -> None:
        self._put_encryption("AES256")
        self._nudge_config_recording("encryption-aes256")

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

    @dry_run_guard("Set default encryption to AES256 (not KMS)")
    def make_kms_encryption_noncompliant(self) -> None:
        self._put_encryption("AES256")
        self._nudge_config_recording("encryption-aes256")

    @dry_run_guard("Set default encryption to aws:kms")
    def make_kms_encryption_compliant(self) -> None:
        self._put_encryption("aws:kms")
        self._nudge_config_recording("encryption-kms")

    @dry_run_guard("Remove required proof tag")
    def make_tagged_noncompliant(self) -> None:
        log(f"Omitting {PROOF_TAG_KEY} on {self.bucket_name}")
        self._put_tags([], "tagged-nc")

    @dry_run_guard("Set required proof tag")
    def make_tagged_compliant(self) -> None:
        log(f"Setting {PROOF_TAG_KEY} on {self.bucket_name}")
        self._put_tags([{"Key": PROOF_TAG_KEY, "Value": "1"}], "tagged-c")

    @dry_run_guard("Clear S3 event notifications")
    def make_events_noncompliant(self) -> None:
        log(f"Clearing event notifications on {self.bucket_name}")
        self.s3.put_bucket_notification_configuration(
            Bucket=self.bucket_name,
            NotificationConfiguration={},
        )
        self._nudge_config_recording("events-off")

    @dry_run_guard("Enable S3 EventBridge notifications")
    def make_events_compliant(self) -> None:
        log(f"Enabling EventBridge notifications on {self.bucket_name}")
        self.s3.put_bucket_notification_configuration(
            Bucket=self.bucket_name,
            NotificationConfiguration={"EventBridgeConfiguration": {}},
        )
        self._nudge_config_recording("events-on")

    def apply_strategy(self, strategy: str, compliant: bool) -> None:
        mapping = {
            "s3_versioning": (
                self.make_versioning_compliant if compliant else self.make_versioning_noncompliant
            ),
            "s3_lifecycle": (
                self.make_lifecycle_compliant if compliant else self.make_lifecycle_noncompliant
            ),
            "s3_version_lifecycle": (
                self.make_version_lifecycle_compliant
                if compliant
                else self.make_version_lifecycle_noncompliant
            ),
            "s3_public_access": (
                self.make_public_access_compliant if compliant else self.make_public_access_noncompliant
            ),
            "s3_public_read": (
                self.make_public_read_compliant if compliant else self.make_public_read_noncompliant
            ),
            "s3_public_write": (
                self.make_public_write_compliant if compliant else self.make_public_write_noncompliant
            ),
            "s3_acl_prohibited": (
                self.make_acl_compliant if compliant else self.make_acl_noncompliant
            ),
            "s3_encryption": (
                self.make_encryption_compliant if compliant else self.make_encryption_noncompliant
            ),
            "s3_kms_encryption": (
                self.make_kms_encryption_compliant if compliant else self.make_kms_encryption_noncompliant
            ),
            "s3_tagged": (
                self.make_tagged_compliant if compliant else self.make_tagged_noncompliant
            ),
            "s3_events": (
                self.make_events_compliant if compliant else self.make_events_noncompliant
            ),
            "s3_generic": (
                self.make_versioning_compliant if compliant else self.make_versioning_noncompliant
            ),
        }
        mapping.get(strategy, mapping["s3_generic"])()
