"""Read-only Config resource-count probe for remaining Storage CP types."""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError
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

INTERESTING = [
    "AWS::Backup::RecoveryPoint",
    "AWS::Backup::BackupVault",
    "AWS::Backup::BackupPlan",
    "AWS::Backup::LogicallyAirGappedBackupVault",
    "AWS::Backup::RestoreTestingPlan",
    "AWS::EC2::SpotFleet",
    "AWS::FSx::FileSystem",
    "AWS::S3Express::DirectoryBucket",
]


@pytest.mark.slow
def test_recorder_inventory(aws_region: str) -> None:
    client = boto3.client("config", region_name=aws_region)
    try:
        status = client.describe_configuration_recorder_status()
        log(f"recorder_status={status}")
    except ClientError as exc:
        log(f"describe_configuration_recorder_status denied: {exc}")

    counts = []
    try:
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
    except ClientError as exc:
        log(f"get_discovered_resource_counts denied: {exc}")
        counts = []

    counts.sort(key=lambda r: r.get("resourceType", ""))
    log(f"total_discovered_types={len(counts)}")
    for c in counts:
        rtype = c.get("resourceType") or ""
        if any(w.lower() in rtype.lower() for w in WATCH):
            log(f"WATCH {rtype} count={c.get('count')}")

    have = {c.get("resourceType") for c in counts}
    for name in INTERESTING:
        present = name in have
        log(f"COUNT {name} present={present}")
        if present:
            continue
        try:
            listed = client.list_discovered_resources(resourceType=name, limit=1)
            ids = listed.get("resourceIdentifiers") or []
            log(f"LIST {name} n={len(ids)} sample={ids[:1]}")
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            log(f"LIST {name} {code}")
