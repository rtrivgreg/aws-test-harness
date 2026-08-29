"""Throwaway EFS pair + mount targets for EFS_MOUNT_TARGET_PUBLIC_ACCESSIBLE.

Does not flip MapPublicIpOnLaunch on existing subnets. Uses one subnet
that already assigns public IPs (NC) and one that does not (C).
"""

from __future__ import annotations

import os
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import log
from harness.tags import PURPOSE_TAG_KEY, PURPOSE_TAG_VALUE, TEST_RUN_ID_TAG_KEY


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

    def _tags(self, name: str) -> list[dict]:
        return [
            {"Key": TEST_RUN_ID_TAG_KEY, "Value": self.test_run_id},
            {"Key": PURPOSE_TAG_KEY, "Value": PURPOSE_TAG_VALUE},
            {"Key": "Name", "Value": name},
            {"Key": "ManagedBy", "Value": "aws-config-test-harness"},
        ]

    def _pick_vpc_and_subnets(self) -> None:
        vpc_id = os.environ.get("HARNESS_VPC_ID", "").strip()
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
        if not public or not private:
            raise RuntimeError(
                f"Need one MapPublicIpOnLaunch=true and one false in {vpc_id}. "
                f"public={len(public)} private={len(private)}. "
                "Set HARNESS_VPC_ID if the default VPC is wrong."
            )
        self.public_subnet_id = public[0]["SubnetId"]
        self.private_subnet_id = private[0]["SubnetId"]
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
