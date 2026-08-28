"""S3_BUCKET_BLACKLISTED_ACTIONS_PROHIBITED — policy allows banned action vs none.

blacklistedActionPatterns includes s3:DeleteBucketPolicy.
A Principal=* Allow of that action is NON_COMPLIANT. No policy is COMPLIANT.
"""

from __future__ import annotations

import json
import time

import boto3
import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.s3_toggle import S3Toggle


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3-bucket-blacklisted-actions-prohibited",
        source_identifier="S3_BUCKET_BLACKLISTED_ACTIONS_PROHIBITED",
        input_parameters={
            "blacklistedActionPatterns": "s3:DeleteBucketPolicy,s3:PutBucketPolicy"
        },
        resource_types=["AWS::S3::Bucket"],
        toggle_strategy="s3_blacklisted_actions",
    )


def _banned_policy(bucket: str) -> str:
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "HarnessBlacklistedAction",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:DeleteBucketPolicy",
            "Resource": f"arn:aws:s3:::{bucket}",
        }],
    })


@pytest.mark.s3
@pytest.mark.slow
def test_s3_bucket_blacklisted_actions_prohibited(
    s3_test_bucket: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    s3_toggle: S3Toggle,
    aws_region: str,
) -> None:
    s3 = boto3.client("s3", region_name=aws_region)
    spec = _spec()
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        s3_toggle.make_public_access_noncompliant()
        rule_name = config_mgr.put_managed_rule(spec, resource_id=s3_test_bucket)

        log(f"Putting blacklisted-action policy on {s3_test_bucket}")
        s3.put_bucket_policy(Bucket=s3_test_bucket, Policy=_banned_policy(s3_test_bucket))
        s3_toggle._nudge_config_recording("blacklisted-on")
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

        log(f"Deleting bucket policy on {s3_test_bucket}")
        try:
            s3.delete_bucket_policy(Bucket=s3_test_bucket)
        except Exception as exc:
            log(f"delete_bucket_policy: {exc}", style="yellow")
        s3_toggle.make_public_access_compliant()
        s3_toggle._nudge_config_recording("blacklisted-off")
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
            timeout_seconds=600,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed blacklisted-actions cycle", style="green")
    finally:
        try:
            s3.delete_bucket_policy(Bucket=s3_test_bucket)
        except Exception:
            pass
        try:
            s3_toggle.make_public_access_compliant()
        except Exception as exc:
            log(f"Cleanup BPA: {exc}", style="yellow")
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
