"""Toggle CloudTrail log file validation."""

from __future__ import annotations

from typing import Optional

import boto3

from harness.dry_run import dry_run_guard, log


class CloudTrailToggle:
    def __init__(self, trail_name: str, region: Optional[str] = None):
        self.trail_name = trail_name
        self.region = region or "us-east-1"
        self.ct = boto3.client("cloudtrail", region_name=self.region)

    @dry_run_guard("Update CloudTrail log file validation")
    def set_log_file_validation(self, enabled: bool) -> None:
        log(f"Set log file validation={enabled} on {self.trail_name}")
        self.ct.update_trail(
            Name=self.trail_name,
            EnableLogFileValidation=enabled,
        )
