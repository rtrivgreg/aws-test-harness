"""S3_BUCKET_POLICY_NOT_MORE_PERMISSIVE — wildcard policy vs no policy.

controlPolicy allows GetObject only for this account. Principal=* GetObject
is more permissive (NON_COMPLIANT). No bucket policy is COMPLIANT.
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


def _control_policy(bucket: str, account: str) -> str:
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "HarnessControl",
            "Effect": "Allow",
            "Principal": {"AWS": f"arn:aws:iam::{account}:root"},
            "Action": "s3:GetObject",
            "Resource": f"arn:aws:s3:::{bucket}/*",
        }],
    }, separators=(",", ":"))


def _wildcard_policy(bucket: str) -> str:
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "HarnessTooOpen",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": f"arn:aws:s3:::{bucket}/*",
        }],
    })


def _spec(bucket: str, account: str) -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3-bucket-policy-not-more-permissive",
        source_identifier="S3_BUCKET_POLICY_NOT_MORE_PERMISSIVE",
        input_parameters={"controlPolicy": _control_policy(bucket, account)},
        resource_types=["AWS::S3::Bucket"],
        toggle_strategy="s3_policy_permissive",
    )


@pytest.mark.s3
@pytest.mark.slow
def test_s3_bucket_policy_not_more_permissive(
    s3_test_bucket: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    s3_toggle: S3Toggle,
    aws_region: str,
) -> None:
    s3 = boto3.client("s3", region_name=aws_region)
    account = boto3.client("sts").get_caller_identity()["Account"]
    spec = _spec(s3_test_bucket, account)
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        s3_toggle.make_public_access_noncompliant()
        rule_name = config_mgr.put_managed_rule(spec, resource_id=s3_test_bucket)

        log(f"Putting more-permissive Principal=* policy on {s3_test_bucket}")
        s3.put_bucket_policy(Bucket=s3_test_bucket, Policy=_wildcard_policy(s3_test_bucket))
        s3_toggle._nudge_config_recording("permissive-open")
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
        s3_toggle._nudge_config_recording("permissive-none")
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
        log(f"{spec.rule_name} passed not-more-permissive cycle", style="green")
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
