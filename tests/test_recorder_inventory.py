"""Read-only Config recorder inventory for remaining Storage CP types."""

from __future__ import annotations

import boto3
import pytest

from harness.dry_run import log

WATCH = (
    "Backup",
    "FSx",
    "S3Express",
    "SpotFleet",
    "Restore",
    "DirectoryBucket",
    "RecoveryPoint",
    "AirGapped",
)


@pytest.mark.slow
def test_recorder_inventory(aws_region: str) -> None:
    client = boto3.client("config", region_name=aws_region)
    status = client.describe_configuration_recorder_status()
    log(f"recorder_status={status}")
    counts = []
    token = None
    while True:
        kwargs = {"limit": 100}
        if token:
            kwargs["nextToken"] = token
        resp = client.get_discovered_resource_counts(**kwargs)
        counts.extend(resp.get("resourceCounts") or [])
        token = resp.get("nextToken")
        if not token:
            break
    counts.sort(key=lambda r: r.get("resourceType", ""))
    watched = [
        c
        for c in counts
        if any(w.lower() in (c.get("resourceType") or "").lower() for w in WATCH)
    ]
    log(f"total_discovered_types={len(counts)}")
    for c in watched:
        log(f"WATCH {c.get('resourceType')} count={c.get('count')}")
    if not watched:
        log("WATCH none of Backup/FSx/S3Express/SpotFleet/Restore/DirectoryBucket")
    interesting = [
        "AWS::Backup::RecoveryPoint",
        "AWS::Backup::BackupVault",
        "AWS::Backup::BackupPlan",
        "AWS::Backup::LogicallyAirGappedBackupVault",
        "AWS::Backup::RestoreTestingPlan",
        "AWS::EC2::SpotFleet",
        "AWS::FSx::FileSystem",
        "AWS::S3Express::DirectoryBucket",
    ]
    have = {c.get("resourceType") for c in counts}
    for name in interesting:
        log(f"PRESENT {name}={name in have}")
