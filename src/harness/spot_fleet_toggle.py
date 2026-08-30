"""Throwaway Spot Fleet requests for EBS Encrypted launch-spec checks.

Uses LaunchSpecifications, not launch templates (the managed rule skips LTs).
TargetCapacity=0 so no instances launch. Always cancel both requests.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import is_dry_run, log
from harness.tags import PURPOSE_TAG_KEY, PURPOSE_TAG_VALUE, TEST_RUN_ID_TAG_KEY

FLEET_ROLE_NAME = "cfg-harness-spot-fleet-role"


def _imds(path: str) -> Optional[str]:
    try:
        req = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            token = resp.read().decode()
        req = urllib.request.Request(
            f"http://169.254.169.254/latest/meta-data/{path}",
            headers={"X-aws-ec2-metadata-token": token},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.read().decode()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


class SpotFleetEncryptHarness:
    def __init__(self, test_run_id: str, region: str = "us-east-1") -> None:
        self.test_run_id = test_run_id
        self.region = region
        self.ec2 = boto3.client("ec2", region_name=region)
        self.iam = boto3.client("iam", region_name=region)
        self.nc_id: Optional[str] = None
        self.c_id: Optional[str] = None
        self.role_arn: Optional[str] = None
        self.created_role = False

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

    def _subnet(self) -> str:
        import os

        subnet = os.environ.get("HARNESS_SUBNET_ID", "").strip()
        if not subnet:
            mac = _imds("mac")
            if mac:
                subnet = _imds(f"network/interfaces/macs/{mac}/subnet-id") or ""
        if not subnet:
            raise RuntimeError("No subnet; set HARNESS_SUBNET_ID")
        return subnet

    def _ensure_role(self) -> str:
        account = boto3.client("sts").get_caller_identity()["Account"]
        arn = f"arn:aws:iam::{account}:role/{FLEET_ROLE_NAME}"
        try:
            self.iam.get_role(RoleName=FLEET_ROLE_NAME)
            self.role_arn = arn
            return arn
        except ClientError:
            pass
        trust = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "spotfleet.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
        self.iam.create_role(
            RoleName=FLEET_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="harness throwaway Spot Fleet role",
            Tags=[
                {"Key": TEST_RUN_ID_TAG_KEY, "Value": self.test_run_id},
                {"Key": PURPOSE_TAG_KEY, "Value": PURPOSE_TAG_VALUE},
            ],
        )
        self.iam.attach_role_policy(
            RoleName=FLEET_ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole",
        )
        self.created_role = True
        self.role_arn = arn
        log(f"Created Spot Fleet role {arn}")
        return arn

    def _request(self, encrypted: bool) -> str:
        name = f"cfg-sfr-{'c' if encrypted else 'nc'}-{self.test_run_id}"
        cfg = {
            "IamFleetRole": self.role_arn,
            "TargetCapacity": 0,
            "Type": "request",
            "AllocationStrategy": "lowestPrice",
            "LaunchSpecifications": [
                {
                    "ImageId": self._ami(),
                    "InstanceType": "t3.nano",
                    "SubnetId": self._subnet(),
                    "WeightedCapacity": 1,
                    "BlockDeviceMappings": [
                        {
                            "DeviceName": "/dev/xvda",
                            "Ebs": {
                                "VolumeSize": 8,
                                "VolumeType": "gp3",
                                "Encrypted": encrypted,
                                "DeleteOnTermination": True,
                            },
                        }
                    ],
                }
            ],
            "TagSpecifications": [
                {
                    "ResourceType": "spot-fleet-request",
                    "Tags": [
                        {"Key": TEST_RUN_ID_TAG_KEY, "Value": self.test_run_id},
                        {"Key": PURPOSE_TAG_KEY, "Value": PURPOSE_TAG_VALUE},
                        {"Key": "Name", "Value": name},
                        {"Key": "ManagedBy", "Value": "aws-config-test-harness"},
                    ],
                }
            ],
        }
        resp = self.ec2.request_spot_fleet(SpotFleetRequestConfig=cfg)
        sfr = resp["SpotFleetRequestId"]
        log(f"SpotFleet {sfr} Encrypted={encrypted} TargetCapacity=0")
        return sfr

    def create_pair(self) -> tuple[str, str]:
        if is_dry_run():
            self.nc_id = "sfr-nc-dry"
            self.c_id = "sfr-c-dry"
            return self.nc_id, self.c_id
        self._ensure_role()
        self.nc_id = self._request(False)
        self.c_id = self._request(True)
        return self.nc_id, self.c_id

    def cleanup(self) -> None:
        ids = [i for i in (self.nc_id, self.c_id) if i and not i.endswith("-dry")]
        if ids:
            try:
                self.ec2.cancel_spot_fleet_requests(
                    SpotFleetRequestIds=ids, TerminateInstances=True
                )
                log(f"Cancelled Spot Fleet requests {ids}")
            except ClientError as exc:
                log(f"cancel_spot_fleet_requests: {exc}", style="yellow")
        if self.created_role:
            try:
                self.iam.detach_role_policy(
                    RoleName=FLEET_ROLE_NAME,
                    PolicyArn="arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole",
                )
                self.iam.delete_role(RoleName=FLEET_ROLE_NAME)
                log(f"Deleted role {FLEET_ROLE_NAME}")
            except ClientError as exc:
                log(f"delete_role ignored: {exc}", style="yellow")
