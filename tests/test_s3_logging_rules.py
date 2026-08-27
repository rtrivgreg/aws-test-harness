"""S3_BUCKET_LOGGING_ENABLED — access logging off then on."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import boto3
import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3-bucket-logging-enabled",
        source_identifier="S3_BUCKET_LOGGING_ENABLED",
        resource_types=["AWS::S3::Bucket"],
        toggle_strategy="s3_logging",
    )


def _logs_bucket() -> str:
    tf_dir = Path("terraform")
    out = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=tf_dir, capture_output=True, text=True, check=True,
        env={**os.environ, "TF_VAR_test_run_id": os.environ.get("TEST_RUN_ID", "")},
    )
    data = json.loads(out.stdout)
    name = (data.get("s3_logs_bucket_name") or {}).get("value")
    assert name, "s3_logs_bucket_name terraform output is empty"
    return name


@pytest.mark.s3
@pytest.mark.slow
def test_s3_bucket_logging_enabled(
    s3_test_bucket: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    s3 = boto3.client("s3", region_name=aws_region)
    target = _logs_bucket()
    spec = _spec()
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        rule_name = config_mgr.put_managed_rule(spec)
        assert spec.source_identifier == "S3_BUCKET_LOGGING_ENABLED"

        log(f"Disabling access logging on {s3_test_bucket}")
        s3.put_bucket_logging(Bucket=s3_test_bucket, BucketLoggingStatus={})
        s3.put_bucket_tagging(
            Bucket=s3_test_bucket,
            Tagging={"TagSet": [
                {"Key": "harness-last-toggle", "Value": "logging-off"},
                {"Key": "harness-toggle-ts", "Value": str(int(time.time()))},
            ]},
        )
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
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        log(f"Enabling access logging {s3_test_bucket} -> {target}")
        s3.put_bucket_logging(
            Bucket=s3_test_bucket,
            BucketLoggingStatus={
                "LoggingEnabled": {
                    "TargetBucket": target,
                    "TargetPrefix": "logs/",
                }
            },
        )
        s3.put_bucket_tagging(
            Bucket=s3_test_bucket,
            Tagging={"TagSet": [
                {"Key": "harness-last-toggle", "Value": "logging-on"},
                {"Key": "harness-toggle-ts", "Value": str(int(time.time()))},
            ]},
        )
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=s3_test_bucket,
            after_timestamp=change_ts,
            resource_type="AWS::S3::Bucket",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=s3_test_bucket,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed logging cycle", style="green")
    finally:
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
