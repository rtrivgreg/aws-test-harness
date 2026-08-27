"""Toggle CloudTrail log file validation and KMS encryption."""

from __future__ import annotations

import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import dry_run_guard, log


class CloudTrailToggle:
    def __init__(
        self,
        trail_name: str,
        trail_arn: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.trail_name = trail_name
        self.trail_arn = trail_arn
        self.region = region or "us-east-1"
        self.ct = boto3.client("cloudtrail", region_name=self.region)

    def _nudge(self, reason: str) -> None:
        if not self.trail_arn:
            return
        log(f"Nudging Config via CloudTrail tag ({reason})")
        self.ct.add_tags(
            ResourceId=self.trail_arn,
            TagsList=[
                {"Key": "harness-toggle-ts", "Value": str(int(time.time()))},
                {"Key": "harness-last-toggle", "Value": reason[:128]},
            ],
        )

    @dry_run_guard("Update CloudTrail log file validation")
    def set_log_file_validation(self, enabled: bool) -> None:
        log(f"Set log file validation={enabled} on {self.trail_name}")
        self.ct.update_trail(
            Name=self.trail_name,
            EnableLogFileValidation=enabled,
        )
        self._nudge("validation-on" if enabled else "validation-off")

    @dry_run_guard("Update CloudTrail KMS encryption")
    def set_kms_encryption(self, kms_key_id: Optional[str]) -> None:
        if kms_key_id:
            log(f"Set trail KmsKeyId={kms_key_id}")
            self.ct.update_trail(Name=self.trail_name, KmsKeyId=kms_key_id)
            self._nudge("kms-on")
            return
        log(f"Clear trail KmsKeyId on {self.trail_name}")
        # Empty string is the documented way to remove SSE-KMS from a trail.
        try:
            self.ct.update_trail(Name=self.trail_name, KmsKeyId="")
        except ClientError as exc:
            log(f"update_trail empty KmsKeyId failed: {exc}", style="yellow")
            raise
        self._nudge("kms-off")
