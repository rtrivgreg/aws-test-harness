"""Throwaway EC2 launch template for EBS-volume-encrypted checks."""

from __future__ import annotations

from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import log
from harness.tags import PURPOSE_TAG_KEY, PURPOSE_TAG_VALUE, TEST_RUN_ID_TAG_KEY


class LaunchTemplateHarness:
    def __init__(self, test_run_id: str, region: Optional[str] = None):
        self.test_run_id = test_run_id
        self.region = region or "us-east-1"
        self.ec2 = boto3.client("ec2", region_name=self.region)
        self.name = f"cfg-lt-{test_run_id}"
        self.template_id: Optional[str] = None

    def _ami(self) -> str:
        imgs = self.ec2.describe_images(
            Owners=["amazon"],
            Filters=[
                {"Name": "name", "Values": ["al2023-ami-*-x86_64"]},
                {"Name": "state", "Values": ["available"]},
            ],
        )["Images"]
        if not imgs:
            raise RuntimeError("No AL2023 AMI found")
        imgs.sort(key=lambda i: i.get("CreationDate", ""), reverse=True)
        return imgs[0]["ImageId"]

    def _data(self, encrypted: bool) -> dict:
        return {
            "ImageId": self._ami(),
            "InstanceType": "t3.nano",
            "BlockDeviceMappings": [{
                "DeviceName": "/dev/xvda",
                "Ebs": {
                    "VolumeSize": 8,
                    "VolumeType": "gp3",
                    "Encrypted": encrypted,
                    "DeleteOnTermination": True,
                },
            }],
        }

    def create_unencrypted(self) -> str:
        resp = self.ec2.create_launch_template(
            LaunchTemplateName=self.name,
            LaunchTemplateData=self._data(encrypted=False),
            TagSpecifications=[{
                "ResourceType": "launch-template",
                "Tags": [
                    {"Key": TEST_RUN_ID_TAG_KEY, "Value": self.test_run_id},
                    {"Key": PURPOSE_TAG_KEY, "Value": PURPOSE_TAG_VALUE},
                    {"Key": "Name", "Value": self.name},
                ],
            }],
        )
        self.template_id = resp["LaunchTemplate"]["LaunchTemplateId"]
        log(f"Created launch template {self.template_id} v1 Encrypted=false")
        return self.template_id

    def set_encrypted_default(self, encrypted: bool) -> int:
        if not self.template_id:
            raise RuntimeError("create_unencrypted first")
        ver = self.ec2.create_launch_template_version(
            LaunchTemplateId=self.template_id,
            LaunchTemplateData=self._data(encrypted=encrypted),
        )["LaunchTemplateVersion"]["VersionNumber"]
        self.ec2.modify_launch_template(
            LaunchTemplateId=self.template_id,
            DefaultVersion=str(ver),
        )
        log(f"Default version {self.template_id} -> v{ver} Encrypted={encrypted}")
        return int(ver)

    def cleanup(self) -> None:
        if not self.template_id:
            return
        try:
            self.ec2.delete_launch_template(LaunchTemplateId=self.template_id)
            log(f"Deleted launch template {self.template_id}")
        except ClientError as exc:
            log(f"delete_launch_template: {exc}", style="yellow")
        self.template_id = None
