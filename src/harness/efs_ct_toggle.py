"""Throwaway EFS pair for EFS_FILESYSTEM_CT_ENCRYPTED."""

from __future__ import annotations

import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import log
from harness.tags import PURPOSE_TAG_KEY, PURPOSE_TAG_VALUE, TEST_RUN_ID_TAG_KEY


class EfsCtHarness:
    def __init__(self, test_run_id: str, region: Optional[str] = None):
        self.test_run_id = test_run_id
        self.region = region or "us-east-1"
        self.efs = boto3.client("efs", region_name=self.region)
        self.unenc_id: Optional[str] = None
        self.enc_id: Optional[str] = None

    def _tags(self, name: str) -> list[dict]:
        return [
            {"Key": TEST_RUN_ID_TAG_KEY, "Value": self.test_run_id},
            {"Key": PURPOSE_TAG_KEY, "Value": PURPOSE_TAG_VALUE},
            {"Key": "Name", "Value": name},
            {"Key": "ManagedBy", "Value": "aws-config-test-harness"},
        ]

    def _wait_available(self, fs_id: str, timeout: int = 180) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            fs = self.efs.describe_file_systems(FileSystemId=fs_id)["FileSystems"][0]
            if fs["LifeCycleState"] == "available":
                return
            time.sleep(3)
        raise TimeoutError(f"{fs_id} not available")

    def create_pair(self) -> tuple[str, str]:
        unenc = self.efs.create_file_system(
            CreationToken=f"cfg-efs-ct-unenc-{self.test_run_id}",
            Encrypted=False,
            ThroughputMode="bursting",
            Backup=False,
            Tags=self._tags(f"cfg-efs-ct-unenc-{self.test_run_id}"),
        )
        self.unenc_id = unenc["FileSystemId"]
        log(f"Created unencrypted EFS {self.unenc_id}")
        enc = self.efs.create_file_system(
            CreationToken=f"cfg-efs-ct-enc-{self.test_run_id}",
            Encrypted=True,
            ThroughputMode="bursting",
            Backup=False,
            Tags=self._tags(f"cfg-efs-ct-enc-{self.test_run_id}"),
        )
        self.enc_id = enc["FileSystemId"]
        log(f"Created encrypted EFS {self.enc_id}")
        self._wait_available(self.unenc_id)
        self._wait_available(self.enc_id)
        return self.unenc_id, self.enc_id

    def cleanup(self) -> None:
        for fs_id in (self.unenc_id, self.enc_id):
            if not fs_id:
                continue
            try:
                self.efs.delete_file_system(FileSystemId=fs_id)
                log(f"Deleted EFS {fs_id}")
            except ClientError as exc:
                log(f"delete_file_system {fs_id}: {exc}", style="yellow")
