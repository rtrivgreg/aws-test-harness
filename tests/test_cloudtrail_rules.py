"""CLOUD_TRAIL_LOG_FILE_VALIDATION_ENABLED on a dedicated harness trail."""

from __future__ import annotations

import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.cloudtrail_toggle import CloudTrailToggle
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="cloud-trail-log-file-validation-enabled",
        source_identifier="CLOUD_TRAIL_LOG_FILE_VALIDATION_ENABLED",
        resource_types=["AWS::CloudTrail::Trail"],
        toggle_strategy="ct_validation",
    )


@pytest.mark.cloudtrail
@pytest.mark.slow
def test_cloudtrail_log_file_validation(
    cloudtrail_trail: dict,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    name = cloudtrail_trail["trail_name"]
    toggle = CloudTrailToggle(trail_name=name, region=aws_region)
    spec = _spec()
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        rule_name = config_mgr.put_managed_rule(spec)

        toggle.set_log_file_validation(False)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=name,
            after_timestamp=change_ts,
            resource_type="AWS::CloudTrail::Trail",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        compliance.assert_resource_compliance(
            rule_name=rule_name,
            resource_id=name,
            expected="NON_COMPLIANT",
            resource_type="AWS::CloudTrail::Trail",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )

        toggle.set_log_file_validation(True)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=name,
            after_timestamp=change_ts,
            resource_type="AWS::CloudTrail::Trail",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        compliance.assert_resource_compliance(
            rule_name=rule_name,
            resource_id=name,
            expected="COMPLIANT",
            resource_type="AWS::CloudTrail::Trail",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )
        log(f"{spec.rule_name} passed validation toggle cycle", style="green")
    finally:
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
