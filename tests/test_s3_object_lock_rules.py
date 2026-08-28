"""S3_BUCKET_DEFAULT_LOCK_ENABLED — existing bucket NC, lock-at-create bucket C.

Object Lock cannot be turned on after create. COMPLIANT uses a throwaway
bucket created with ObjectLockEnabledForBucket=True.
"""

from __future__ import annotations

import time

import boto3
import pytest
from botocore.exceptions import ClientError

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.s3_toggle import S3Toggle


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3-bucket-default-lock-enabled",
        source_identifier="S3_BUCKET_DEFAULT_LOCK_ENABLED",
        resource_types=["AWS::S3::Bucket"],
        toggle_strategy="s3_object_lock",
    )


def _empty_and_delete(s3, bucket: str) -> None:
    try:
        paginator = s3.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=bucket):
            objs = []
            for v in page.get("Versions", []) + page.get("DeleteMarkers", []):
                item = {"Key": v["Key"]}
                if "VersionId" in v:
                    item["VersionId"] = v["VersionId"]
                objs.append(item)
            if objs:
                s3.delete_objects(Bucket=bucket, Delete={"Objects": objs, "Quiet": True})
    except ClientError:
        pass
    try:
        s3.delete_bucket(Bucket=bucket)
        log(f"Deleted lock bucket {bucket}")
    except ClientError as exc:
        log(f"delete lock bucket: {exc}", style="yellow")


@pytest.mark.s3
@pytest.mark.slow
def test_s3_bucket_default_lock_enabled(
    s3_test_bucket: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    s3_toggle: S3Toggle,
    aws_region: str,
) -> None:
    s3 = boto3.client("s3", region_name=aws_region)
    lock_bucket = f"cfg-test-lock-{s3_test_bucket[-8:]}"
    spec = _spec()
    rule_name = None
    created = False
    try:
        log(f"===== Testing rule: {spec.rule_name} =====")
        rule_name = config_mgr.put_managed_rule(spec, resource_id=s3_test_bucket)
        s3_toggle._nudge_config_recording("lock-absent")
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=s3_test_bucket,
            after_timestamp=change_ts,
            resource_type="AWS::S3::Bucket",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=s3_test_bucket,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=600,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        log(f"Creating Object-Lock bucket {lock_bucket}")
        s3.create_bucket(
            Bucket=lock_bucket,
            ObjectLockEnabledForBucket=True,
        )
        created = True
        s3.put_bucket_tagging(
            Bucket=lock_bucket,
            Tagging={"TagSet": [
                {"Key": "Purpose", "Value": "aws-config-rule-testing"},
                {"Key": "test-run-id", "Value": "ef57dcf4"},
            ]},
        )
        compliance.wait_for_resource_discovered(
            resource_id=lock_bucket, resource_type="AWS::S3::Bucket"
        )
        rule_name = config_mgr.put_managed_rule(spec, resource_id=lock_bucket)
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=lock_bucket,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=600,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed object-lock cycle", style="green")
    finally:
        if created:
            _empty_and_delete(s3, lock_bucket)
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
