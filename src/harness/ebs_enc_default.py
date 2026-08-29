"""Region EBS encryption-by-default toggle."""

from __future__ import annotations

from typing import Optional

import boto3

from harness.dry_run import log


class EbsEncryptionByDefault:
    def __init__(self, region: Optional[str] = None):
        self.region = region or "us-east-1"
        self.ec2 = boto3.client("ec2", region_name=self.region)

    def enabled(self) -> bool:
        return bool(self.ec2.get_ebs_encryption_by_default().get("EbsEncryptionByDefault"))

    def set(self, on: bool) -> bool:
        if on:
            log("Enable EBS encryption by default")
            self.ec2.enable_ebs_encryption_by_default()
        else:
            log("Disable EBS encryption by default")
            self.ec2.disable_ebs_encryption_by_default()
        state = self.enabled()
        log(f"EBS encryption by default={state}")
        return state
