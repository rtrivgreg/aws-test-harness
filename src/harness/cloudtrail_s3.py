"""Ensure a harness multi-Region trail can write to the logs bucket."""

from __future__ import annotations

import json
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import log


def logs_bucket_name(test_bucket: str, test_run_id: str) -> str:
    explicit = __import__("os").environ.get("S3_LOGS_BUCKET")
    if explicit:
        return explicit
    if "logs" in test_bucket:
        return test_bucket
    if test_bucket.startswith("cfg-test-"):
        return test_bucket.replace("cfg-test-", "cfg-test-logs-", 1)
    return f"cfg-test-logs-{test_run_id}"


def ensure_cloudtrail_bucket_policy(bucket: str, account: str, region: str) -> None:
    s3 = boto3.client("s3", region_name=region)
    try:
        raw = s3.get_bucket_policy(Bucket=bucket)["Policy"]
        policy = json.loads(raw)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in ("NoSuchBucketPolicy",):
            raise
        policy = {"Version": "2012-10-17", "Statement": []}
    statements = policy.setdefault("Statement", [])
    sid_write = "HarnessCloudTrailWrite"
    sid_acl = "HarnessCloudTrailAcl"
    statements = [s for s in statements if s.get("Sid") not in (sid_write, sid_acl)]
    statements.append({
        "Sid": sid_acl,
        "Effect": "Allow",
        "Principal": {"Service": "cloudtrail.amazonaws.com"},
        "Action": "s3:GetBucketAcl",
        "Resource": f"arn:aws:s3:::{bucket}",
    })
    statements.append({
        "Sid": sid_write,
        "Effect": "Allow",
        "Principal": {"Service": "cloudtrail.amazonaws.com"},
        "Action": "s3:PutObject",
        "Resource": f"arn:aws:s3:::{bucket}/AWSLogs/{account}/*",
        "Condition": {"StringEquals": {"s3:x-amz-acl": "bucket-owner-full-control"}},
    })
    policy["Statement"] = statements
    log(f"Putting CloudTrail write policy on {bucket}")
    s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))


def ensure_harness_trail(
    region: str,
    test_run_id: str,
    test_bucket: str,
) -> tuple[str, Optional[str], bool]:
    """Return (name, arn, created)."""
    ct = boto3.client("cloudtrail", region_name=region)
    sts = boto3.client("sts")
    account = sts.get_caller_identity()["Account"]
    for t in ct.describe_trails().get("trailList") or []:
        name = t.get("Name") or ""
        if name.startswith("cfg-ct-") or test_run_id in name:
            log(f"Using harness trail {name} multi={t.get('IsMultiRegionTrail')}")
            return name, t.get("TrailARN"), False
    bucket = logs_bucket_name(test_bucket, test_run_id)
    ensure_cloudtrail_bucket_policy(bucket, account, region)
    name = f"cfg-ct-s3w-{test_run_id}"
    log(f"Creating throwaway trail {name} -> s3://{bucket}")
    created = ct.create_trail(
        Name=name,
        S3BucketName=bucket,
        IsMultiRegionTrail=True,
        EnableLogFileValidation=True,
    )
    ct.start_logging(Name=name)
    return name, created.get("TrailARN"), True
