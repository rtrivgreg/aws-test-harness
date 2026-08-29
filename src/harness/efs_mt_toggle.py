"""Throwaway EFS pair + mount targets for EFS_MOUNT_TARGET_PUBLIC_ACCESSIBLE.

Does not flip MapPublicIpOnLaunch on existing subnets. Prefers the instance
VPC over the account default VPC. If that VPC has no private subnet, creates
a tagged /28 with MapPublicIpOnLaunch=false and deletes it on cleanup.
"""

from __future__ import annotations

import ipaddress
import os
import time
import urllib.error
import urllib.request
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import log
from harness.tags import PURPOSE_TAG_KEY, PURPOSE_TAG_VALUE, TEST_RUN_ID_TAG_KEY


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


class EfsMountTargetHarness:
    def __init__(self, test_run_id: str, region: Optional[str] = None):
        self.test_run_id = test_run_id
        self.region = region or "us-east-1"
        self.efs = boto3.client("efs", region_name=self.region)
        self.ec2 = boto3.client("ec2", region_name=self.region)
        self.nc_fs_id: Optional[str] = None
        self.c_fs_id: Optional[str] = None
        self.nc_mt_id: Optional[str] = None
        self.c_mt_id: Optional[str] = None
        self.sg_id: Optional[str] = None
        self.vpc_id: Optional[str] = None
        self.public_subnet_id: Optional[str] = None
        self.private_subnet_id: Optional[str] = None
        self.created_private_subnet_id: Optional[str] = None

    def _tags(self, name: str) -> list[dict]:
        return [
            {"Key": TEST_RUN_ID_TAG_KEY, "Value": self.test_run_id},
            {"Key": PURPOSE_TAG_KEY, "Value": PURPOSE_TAG_VALUE},
            {"Key": "Name", "Value": name},
            {"Key": "ManagedBy", "Value": "aws-config-test-harness"},
        ]

    def _instance_vpc_id(self) -> Optional[str]:
        mac = _imds("mac")
        if not mac:
            return None
        return _imds(f"network/interfaces/macs/{mac}/vpc-id")

    def _free_slash28(self, vpc_cidr: str, used: list[str]) -> str:
        vpc = ipaddress.ip_network(vpc_cidr)
        taken = [ipaddress.ip_network(c) for c in used]
        for candidate in vpc.subnets(new_prefix=28):
            if any(candidate.overlaps(t) for t in taken):
                continue
            return str(candidate)
        raise RuntimeError(f"No free /28 in {vpc_cidr}")

    def _create_private_subnet(self, vpc_id: str, subnets: list[dict]) -> str:
        vpc = self.ec2.describe_vpcs(VpcIds=[vpc_id])["Vpcs"][0]
        cidr = vpc["CidrBlock"]
        used = [s["CidrBlock"] for s in subnets]
        block = self._free_slash28(cidr, used)
        az = subnets[0]["AvailabilityZone"] if subnets else None
        kwargs = {
            "VpcId": vpc_id,
            "CidrBlock": block,
            "TagSpecifications": [
                {
                    "ResourceType": "subnet",
                    "Tags": self._tags(f"cfg-efs-mt-priv-{self.test_run_id}"),
                }
            ],
        }
        if az:
            kwargs["AvailabilityZone"] = az
        created = self.ec2.create_subnet(**kwargs)
        subnet_id = created["Subnet"]["SubnetId"]
        self.ec2.modify_subnet_attribute(
            SubnetId=subnet_id, MapPublicIpOnLaunch={"Value": False}
        )
        self.created_private_subnet_id = subnet_id
        log(f"Created private subnet {subnet_id} {block} in {vpc_id}")
        return subnet_id

    def _pick_vpc_and_subnets(self) -> None:
        vpc_id = os.environ.get("HARNESS_VPC_ID", "").strip()
        if not vpc_id:
            vpc_id = self._instance_vpc_id() or ""
        if not vpc_id:
            defaults = self.ec2.describe_vpcs(
                Filters=[{"Name": "is-default", "Values": ["true"]}]
            ).get("Vpcs", [])
            if defaults:
                vpc_id = defaults[0]["VpcId"]
            else:
                vpcs = self.ec2.describe_vpcs().get("Vpcs", [])
                if not vpcs:
                    raise RuntimeError("No VPC found for mount-target harness")
                vpc_id = vpcs[0]["VpcId"]
        self.vpc_id = vpc_id
        subnets = self.ec2.describe_subnets(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        ).get("Subnets", [])
        public = [s for s in subnets if s.get("MapPublicIpOnLaunch")]
        private = [s for s in subnets if not s.get("MapPublicIpOnLaunch")]
        if not public:
            raise RuntimeError(
                f"No MapPublicIpOnLaunch=true subnet in {vpc_id}. "
                "Set HARNESS_VPC_ID to a VPC that already has one."
            )
        self.public_subnet_id = public[0]["SubnetId"]
        if private:
            self.private_subnet_id = private[0]["SubnetId"]
        else:
            self.private_subnet_id = self._create_private_subnet(vpc_id, subnets)
        log(
            f"VPC {vpc_id} public_subnet={self.public_subnet_id} "
            f"private_subnet={self.private_subnet_id}"
        )

    def _ensure_sg(self) -> str:
        name = f"cfg-efs-mt-{self.test_run_id}"
        created = self.ec2.create_security_group(
            GroupName=name,
            Description="harness EFS mount target",
            VpcId=self.vpc_id,
            TagSpecifications=[
                {
                    "ResourceType": "security-group",
                    "Tags": self._tags(name),
                }
            ],
        )
        self.sg_id = created["GroupId"]
        self.ec2.authorize_security_group_ingress(
            GroupId=self.sg_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 2049,
                    "ToPort": 2049,
                    "UserIdGroupPairs": [{"GroupId": self.sg_id}],
                }
            ],
        )
        log(f"Created SG {self.sg_id}")
        return self.sg_id

    def _wait_fs(self, fs_id: str, timeout: int = 180) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            fs = self.efs.describe_file_systems(FileSystemId=fs_id)["FileSystems"][0]
            if fs["LifeCycleState"] == "available":
                return
            time.sleep(3)
        raise TimeoutError(f"{fs_id} not available")

    def _wait_mt(self, mt_id: str, timeout: int = 180) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            mts = self.efs.describe_mount_targets(MountTargetId=mt_id).get(
                "MountTargets", []
            )
            if mts and mts[0]["LifeCycleState"] == "available":
                return
            time.sleep(3)
        raise TimeoutError(f"mount target {mt_id} not available")

    def create_pair(self) -> tuple[str, str]:
        self._pick_vpc_and_subnets()
        self._ensure_sg()
        nc = self.efs.create_file_system(
            CreationToken=f"cfg-efs-mt-nc-{self.test_run_id}",
            Encrypted=True,
            ThroughputMode="bursting",
            Backup=False,
            Tags=self._tags(f"cfg-efs-mt-nc-{self.test_run_id}"),
        )
        self.nc_fs_id = nc["FileSystemId"]
        c = self.efs.create_file_system(
            CreationToken=f"cfg-efs-mt-c-{self.test_run_id}",
            Encrypted=True,
            ThroughputMode="bursting",
            Backup=False,
            Tags=self._tags(f"cfg-efs-mt-c-{self.test_run_id}"),
        )
        self.c_fs_id = c["FileSystemId"]
        log(f"Created EFS nc={self.nc_fs_id} c={self.c_fs_id}")
        self._wait_fs(self.nc_fs_id)
        self._wait_fs(self.c_fs_id)
        nc_mt = self.efs.create_mount_target(
            FileSystemId=self.nc_fs_id,
            SubnetId=self.public_subnet_id,
            SecurityGroups=[self.sg_id],
        )
        self.nc_mt_id = nc_mt["MountTargetId"]
        c_mt = self.efs.create_mount_target(
            FileSystemId=self.c_fs_id,
            SubnetId=self.private_subnet_id,
            SecurityGroups=[self.sg_id],
        )
        self.c_mt_id = c_mt["MountTargetId"]
        log(
            f"Mount targets nc={self.nc_mt_id}@{self.public_subnet_id} "
            f"c={self.c_mt_id}@{self.private_subnet_id}"
        )
        self._wait_mt(self.nc_mt_id)
        self._wait_mt(self.c_mt_id)
        return self.nc_fs_id, self.c_fs_id

    def _delete_mt(self, mt_id: Optional[str]) -> None:
        if not mt_id:
            return
        try:
            self.efs.delete_mount_target(MountTargetId=mt_id)
            log(f"Deleted mount target {mt_id}")
        except ClientError as exc:
            log(f"delete_mount_target {mt_id}: {exc}", style="yellow")
            return
        deadline = time.time() + 180
        while time.time() < deadline:
            try:
                mts = self.efs.describe_mount_targets(MountTargetId=mt_id).get(
                    "MountTargets", []
                )
                if not mts or mts[0]["LifeCycleState"] == "deleted":
                    return
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("MountTargetNotFound", "FileSystemNotFound"):
                    return
                log(f"describe_mount_targets {mt_id}: {exc}", style="yellow")
                return
            time.sleep(3)

    def cleanup(self) -> None:
        self._delete_mt(self.nc_mt_id)
        self._delete_mt(self.c_mt_id)
        for fs_id in (self.nc_fs_id, self.c_fs_id):
            if not fs_id:
                continue
            try:
                self.efs.delete_file_system(FileSystemId=fs_id)
                log(f"Deleted EFS {fs_id}")
            except ClientError as exc:
                log(f"delete_file_system {fs_id}: {exc}", style="yellow")
        if self.sg_id:
            try:
                self.ec2.delete_security_group(GroupId=self.sg_id)
                log(f"Deleted SG {self.sg_id}")
            except ClientError as exc:
                log(f"delete_security_group {self.sg_id}: {exc}", style="yellow")
        if self.created_private_subnet_id:
            try:
                self.ec2.delete_subnet(SubnetId=self.created_private_subnet_id)
                log(f"Deleted private subnet {self.created_private_subnet_id}")
            except ClientError as exc:
                log(
                    f"delete_subnet {self.created_private_subnet_id}: {exc}",
                    style="yellow",
                )
