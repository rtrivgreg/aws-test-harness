"""Toggle FSx OpenZFS copy-tags flags."""

from __future__ import annotations

from typing import Optional

import boto3

from harness.dry_run import dry_run_guard, log


class FsxToggle:
    def __init__(self, file_system_id: str, region: Optional[str] = None):
        self.file_system_id = file_system_id
        self.region = region or "us-east-1"
        self.fsx = boto3.client("fsx", region_name=self.region)

    @dry_run_guard("Update FSx OpenZFS copy tags")
    def set_copy_tags(self, enabled: bool) -> None:
        log(f"Set FSx copy_tags={enabled} on {self.file_system_id}")
        self.fsx.update_file_system(
            FileSystemId=self.file_system_id,
            OpenZFSConfiguration={
                "CopyTagsToBackups": enabled,
                "CopyTagsToVolumes": enabled,
            },
        )
