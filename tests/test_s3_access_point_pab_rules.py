"""S3_ACCESS_POINT_PUBLIC_ACCESS_BLOCKS — temp AP on the harness test bucket.

NC: all four AP block-public flags false. C: all four true.
Deletes the access point in finally.
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


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3-access-point-public-access-blocks",
        source_identifier="S3_ACCESS_POINT_PUBLIC_ACCESS_BLOCKS",
        resource_types=["AWS::S3::AccessPoint"],
        toggle_strategy="s3_ap_pab",
    )


def _pab(locked: bool) -> dict:
    flag = locked
    return {
        "BlockPublicAcls": flag,
        "IgnorePublicAcls": flag,
        "BlockPublicPolicy": flag,
        "RestrictPublicBuckets": flag,
    }


@pytest.mark.s3
@pytest.mark.slow
def test_s3_access_point_public_access_blocks(
    s3_test_bucket: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    account = boto3.client("sts").get_caller_identity()["Account"]
    s3c = boto3.client("s3control", region_name=aws_region)
    ap_name = f"harness-ap-{s3_test_bucket[-8:]}"
    spec = _spec()
    rule_name = None
    created = False
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        try:
            s3c.create_access_point(
                AccountId=account,
                Name=ap_name,
                Bucket=s3_test_bucket,
                PublicAccessBlockConfiguration=_pab(False),
            )
            created = True
            log(f"Created access point {ap_name} on {s3_test_bucket} (PAB off)")
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "AccessPointAlreadyOwnedByYou":
                raise
            created = True
            s3c.put_access_point_public_access_block(
                AccountId=account,
                Name=ap_name,
                PublicAccessBlockConfiguration=_pab(False),
            )
            log(f"Reused access point {ap_name} (PAB off)")

        compliance.wait_for_resource_discovered(
            resource_id=ap_name, resource_type="AWS::S3::AccessPoint"
        )
        rule_name = config_mgr.put_managed_rule(spec, resource_id=ap_name)

        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=ap_name,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=600,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        log(f"Locking PAB on access point {ap_name}")
        s3c.put_access_point_public_access_block(
            AccountId=account,
            Name=ap_name,
            PublicAccessBlockConfiguration=_pab(True),
        )
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=ap_name,
            after_timestamp=change_ts,
            resource_type="AWS::S3::AccessPoint",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=ap_name,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=600,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed access-point PAB cycle", style="green")
    finally:
        if created:
            try:
                s3c.delete_access_point(AccountId=account, Name=ap_name)
                log(f"Deleted access point {ap_name}")
            except Exception as exc:
                log(f"Cleanup AP: {exc}", style="yellow")
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
