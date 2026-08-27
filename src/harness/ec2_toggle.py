"""Toggle EC2 instance metadata HTTP tokens (IMDSv2)."""

from __future__ import annotations

from typing import Optional

import boto3

from harness.dry_run import dry_run_guard, log


class Ec2Toggle:
    def __init__(self, instance_id: str, region: Optional[str] = None):
        self.instance_id = instance_id
        self.region = region or "us-east-1"
        self.ec2 = boto3.client("ec2", region_name=self.region)

    @dry_run_guard("Modify instance metadata options")
    def set_imdsv2_required(self, required: bool) -> None:
        tokens = "required" if required else "optional"
        log(f"Set HttpTokens={tokens} on {self.instance_id}")
        self.ec2.modify_instance_metadata_options(
            InstanceId=self.instance_id,
            HttpTokens=tokens,
            HttpEndpoint="enabled",
        )
