"""Throwaway EC2 pair for EBS_OPTIMIZED_INSTANCE.

Current-generation types are EBS-optimized by default and always evaluate
COMPLIANT. NON_COMPLIANT requires a type whose EbsOptimizedSupport is
'supported' (optional), launched with EbsOptimized=false.
"""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import log
from harness.tags import PURPOSE_TAG_KEY, PURPOSE_TAG_VALUE, TEST_RUN_ID_TAG_KEY

PREFERRED_OPTIONAL = (
    "m4.large",
    "c4.large",
    "r4.large",
    "m4.xlarge",
    "c3.large",
    "m3.medium",
)


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


class EbsOptimizedHarness:
    def __init__(self, test_run_id: str, region: Optional[str] = None):
        self.test_run_id = test_run_id
        self.region = region or "us-east-1"
        self.ec2 = boto3.client("ec2", region_name=self.region)
        self.nc_id: Optional[str] = None
        self.c_id: Optional[str] = None
        self.sg_id: Optional[str] = None
        self.subnet_id: Optional[str] = None
        self.optional_type: Optional[str] = None

    def _tags(self, name: str) -> list[dict]:
        return [
            {"Key": TEST_RUN_ID_TAG_KEY, "Value": self.test_run_id},
            {"Key": PURPOSE_TAG_KEY, "Value": PURPOSE_TAG_VALUE},
            {"Key": "Name", "Value": name},
            {"Key": "ManagedBy", "Value": "aws-config-test-harness"},
        ]

    def _tag_spec(self, resource_type: str, name: str) -> list[dict]:
        return [{"ResourceType": resource_type, "Tags": self._tags(name)}]

    def _al2_ami(self) -> str:
        imgs = self.ec2.describe_images(
            Owners=["amazon"],
            Filters=[
                {"Name": "name", "Values": ["amzn2-ami-hvm-*-x86_64-gp2"]},
                {"Name": "state", "Values": ["available"]},
            ],
        )["Images"]
        if not imgs:
            raise RuntimeError("No Amazon Linux 2 AMI found")
        imgs.sort(key=lambda i: i.get("CreationDate", ""), reverse=True)
        return imgs[0]["ImageId"]

    def _al2023_ami(self) -> str:
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

    def _support_for(self, instance_type: str) -> Optional[str]:
        try:
            types = self.ec2.describe_instance_types(InstanceTypes=[instance_type]).get(
                "InstanceTypes", []
            )
        except ClientError as exc:
            log(f"describe_instance_types {instance_type}: {exc}", style="yellow")
            return None
        if not types:
            return None
        return ((types[0].get("EbsInfo") or {}).get("EbsOptimizedSupport") or "").lower()

    def _scan_optional_types(self) -> list[str]:
        names: list[str] = []
        token = None
        while True:
            kwargs = {
                "Filters": [
                    {
                        "Name": "ebs-info.ebs-optimized-support",
                        "Values": ["supported"],
                    }
                ]
            }
            if token:
                kwargs["NextToken"] = token
            resp = self.ec2.describe_instance_types(**kwargs)
            for t in resp.get("InstanceTypes", []):
                names.append(t["InstanceType"])
            token = resp.get("NextToken")
            if not token:
                break
        names.sort()
        log(f"Region optional EBS-optimized types ({len(names)}): {names[:20]}")
        return names

    def _pick_optional_type(self) -> str:
        forced = os.environ.get("HARNESS_EBS_OPT_TYPE", "").strip()
        if forced:
            support = self._support_for(forced)
            if support == "supported":
                log(f"Using HARNESS_EBS_OPT_TYPE={forced}")
                return forced
            raise RuntimeError(
                f"HARNESS_EBS_OPT_TYPE={forced} EbsOptimizedSupport={support}"
            )
        for name in PREFERRED_OPTIONAL:
            support = self._support_for(name)
            log(f"{name} EbsOptimizedSupport={support}")
            if support == "supported":
                return name
        scanned = self._scan_optional_types()
        if scanned:
            chosen = scanned[0]
            log(f"Using first regional optional type {chosen}")
            return chosen
        raise RuntimeError(
            "No instance type in this region has EbsOptimizedSupport=supported. "
            "Park EBS_OPTIMIZED_INSTANCE: current-gen types are default-on and "
            "the rule always returns COMPLIANT for them."
        )

    def _placement(self) -> tuple[str, str]:
        subnet = os.environ.get("HARNESS_SUBNET_ID", "").strip()
        if not subnet:
            mac = _imds("mac")
            if mac:
                subnet = _imds(f"network/interfaces/macs/{mac}/subnet-id") or ""
        if not subnet:
            raise RuntimeError("No subnet; set HARNESS_SUBNET_ID")
        vpc = self.ec2.describe_subnets(SubnetIds=[subnet])["Subnets"][0]["VpcId"]
        return subnet, vpc

    def _ensure_sg(self, vpc_id: str) -> str:
        name = f"cfg-ebs-opt-{self.test_run_id}"
        created = self.ec2.create_security_group(
            GroupName=name,
            Description="harness EBS optimized instances - no inbound",
            VpcId=vpc_id,
            TagSpecifications=self._tag_spec("security-group", name),
        )
        self.sg_id = created["GroupId"]
        log(f"Created SG {self.sg_id}")
        return self.sg_id

    def _wait_running(self, instance_id: str, timeout: int = 300) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            inst = self.ec2.describe_instances(InstanceIds=[instance_id])[
                "Reservations"
            ][0]["Instances"][0]
            state = inst["State"]["Name"]
            log(f"{instance_id} state={state}")
            if state == "running":
                return
            if state in ("terminated", "shutting-down"):
                raise RuntimeError(f"{instance_id} entered {state}")
            time.sleep(5)
        raise TimeoutError(f"{instance_id} not running")

    def _run(
        self, *, name: str, image_id: str, instance_type: str, ebs_optimized: bool
    ) -> str:
        resp = self.ec2.run_instances(
            ImageId=image_id,
            InstanceType=instance_type,
            MinCount=1,
            MaxCount=1,
            SubnetId=self.subnet_id,
            SecurityGroupIds=[self.sg_id],
            EbsOptimized=ebs_optimized,
            InstanceInitiatedShutdownBehavior="terminate",
            TagSpecifications=self._tag_spec("instance", name),
        )
        iid = resp["Instances"][0]["InstanceId"]
        log(
            f"Launched {iid} type={instance_type} EbsOptimized={ebs_optimized}"
        )
        return iid

    def create_pair(self) -> tuple[str, str]:
        self.optional_type = self._pick_optional_type()
        self.subnet_id, vpc_id = self._placement()
        self._ensure_sg(vpc_id)
        al2 = self._al2_ami()
        al2023 = self._al2023_ami()
        self.nc_id = self._run(
            name=f"cfg-ebs-opt-nc-{self.test_run_id}",
            image_id=al2,
            instance_type=self.optional_type,
            ebs_optimized=False,
        )
        self.c_id = self._run(
            name=f"cfg-ebs-opt-c-{self.test_run_id}",
            image_id=al2023,
            instance_type="t3.nano",
            ebs_optimized=True,
        )
        self._wait_running(self.nc_id)
        self._wait_running(self.c_id)
        return self.nc_id, self.c_id

    def cleanup(self) -> None:
        ids = [i for i in (self.nc_id, self.c_id) if i]
        if ids:
            try:
                self.ec2.terminate_instances(InstanceIds=ids)
                log(f"Terminated {ids}")
                waiter = self.ec2.get_waiter("instance_terminated")
                waiter.wait(InstanceIds=ids)
            except ClientError as exc:
                log(f"terminate_instances: {exc}", style="yellow")
        if self.sg_id:
            try:
                self.ec2.delete_security_group(GroupId=self.sg_id)
                log(f"Deleted SG {self.sg_id}")
            except ClientError as exc:
                log(f"delete_security_group {self.sg_id}: {exc}", style="yellow")
