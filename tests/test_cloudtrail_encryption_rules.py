"""CLOUD_TRAIL_ENCRYPTION_ENABLED — requires CLOUDTRAIL_KMS_KEY_ARN."""

from __future__ import annotations

import os
import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.cloudtrail_toggle import CloudTrailToggle
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="cloud-trail-encryption-enabled",
        source_identifier="CLOUD_TRAIL_ENCRYPTION_ENABLED",
        resource_types=["AWS::CloudTrail::Trail"],
        toggle_strategy="ct_kms",
    )


def _resource_ids(trail: dict) -> list[str]:
    ids = [trail["trail_name"]]
    if trail.get("trail_arn"):
        ids.append(trail["trail_arn"])
    return ids


@pytest.mark.cloudtrail
@pytest.mark.slow
def test_cloudtrail_encryption_enabled(
    cloudtrail_trail: dict,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    key_arn = os.environ.get("CLOUDTRAIL_KMS_KEY_ARN")
    if not key_arn:
        pytest.skip("Set CLOUDTRAIL_KMS_KEY_ARN to the symmetric CMK ARN")

    name = cloudtrail_trail["trail_name"]
    toggle = CloudTrailToggle(
        trail_name=name,
        trail_arn=cloudtrail_trail.get("trail_arn"),
        region=aws_region,
    )
    spec = _spec()
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        rule_name = config_mgr.put_managed_rule(spec)

        toggle.set_kms_encryption(None)
        change_ts = time.time()
        _assert_leg(
            compliance,
            config_mgr,
            rule_name,
            cloudtrail_trail,
            change_ts,
            "NON_COMPLIANT",
        )

        toggle.set_kms_encryption(key_arn)
        change_ts = time.time()
        _assert_leg(
            compliance,
            config_mgr,
            rule_name,
            cloudtrail_trail,
            change_ts,
            "COMPLIANT",
        )
        log(f"{spec.rule_name} passed KMS toggle cycle", style="green")
    finally:
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")


def _assert_leg(compliance, config_mgr, rule_name, trail, change_ts, expected):
    last_err = None
    for rid in _resource_ids(trail):
        try:
            compliance.wait_for_config_item_after(
                resource_id=rid,
                after_timestamp=change_ts,
                resource_type="AWS::CloudTrail::Trail",
                timeout_seconds=180,
            )
            eval_ts = time.time()
            config_mgr.start_evaluation(rule_name)
            config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
            compliance.assert_resource_compliance(
                rule_name=rule_name,
                resource_id=rid,
                expected=expected,
                resource_type="AWS::CloudTrail::Trail",
                config_mgr=config_mgr,
                after_timestamp=eval_ts,
            )
            return
        except Exception as exc:
            last_err = exc
            log(f"id {rid} did not work yet: {exc}", style="yellow")
    raise last_err
