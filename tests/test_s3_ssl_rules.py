"""S3_BUCKET_SSL_REQUESTS_ONLY — deny-insecure-transport policy on/off."""

from __future__ import annotations

import json
import time

import boto3
import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3-bucket-ssl-requests-only",
        source_identifier="S3_BUCKET_SSL_REQUESTS_ONLY",
        resource_types=["AWS::S3::Bucket"],
        toggle_strategy="s3_ssl_only",
    )


def _ssl_policy(bucket: str) -> str:
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "DenyInsecureTransport",
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:*",
            "Resource": [
                f"arn:aws:s3:::{bucket}",
                f"arn:aws:s3:::{bucket}/*",
            ],
            "Condition": {"Bool": {"aws:SecureTransport": "false"}},
        }],
    })


@pytest.mark.s3
@pytest.mark.slow
def test_s3_bucket_ssl_requests_only(
    s3_test_bucket: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    s3 = boto3.client("s3", region_name=aws_region)
    spec = _spec()
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        rule_name = config_mgr.put_managed_rule(spec)
        assert rule_name
        assert spec.source_identifier == "S3_BUCKET_SSL_REQUESTS_ONLY"

        log(f"Removing bucket policy on {s3_test_bucket}")
        try:
            s3.delete_bucket_policy(Bucket=s3_test_bucket)
        except Exception as exc:
            log(f"delete_bucket_policy: {exc}", style="yellow")
        s3.put_bucket_tagging(
            Bucket=s3_test_bucket,
            Tagging={"TagSet": [
                {"Key": "harness-last-toggle", "Value": "ssl-policy-removed"},
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

        log(f"Putting SSL-only policy on {s3_test_bucket}")
        s3.put_bucket_policy(Bucket=s3_test_bucket, Policy=_ssl_policy(s3_test_bucket))
        s3.put_bucket_tagging(
            Bucket=s3_test_bucket,
            Tagging={"TagSet": [
                {"Key": "harness-last-toggle", "Value": "ssl-policy-applied"},
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
        log(f"{spec.rule_name} passed SSL-only cycle", style="green")
    finally:
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
