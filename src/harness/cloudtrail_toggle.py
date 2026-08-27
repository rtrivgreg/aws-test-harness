"""Toggle CloudTrail log file validation."""

from __future__ import annotations

import time
from typing import Optional

import boto3

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
        arn = self.trail_arn
        if not arn:
            return
        log(f"Nudging Config via CloudTrail tag ({reason})")
        self.ct.add_tags(
            ResourceId=arn,
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
