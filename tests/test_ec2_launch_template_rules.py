"""EC2_LAUNCH_TEMPLATES_EBS_VOLUME_ENCRYPTED — LT default version off/on.

Change-triggered. No Terraform. No Backup APIs.
"""

from __future__ import annotations

import os
import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.lt_toggle import LaunchTemplateHarness


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="ec2-launch-templates-ebs-volume-encrypted",
        source_identifier="EC2_LAUNCH_TEMPLATES_EBS_VOLUME_ENCRYPTED",
        input_parameters={},
        resource_types=["AWS::EC2::LaunchTemplate"],
        toggle_strategy="lt_ebs_encrypted",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> None:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}")
    log(f"EvaluationResults ({len(rows)}): {rows}")


@pytest.mark.ec2
@pytest.mark.ebs
@pytest.mark.slow
def test_ec2_launch_templates_ebs_volume_encrypted(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    harness = LaunchTemplateHarness(test_run_id=test_run_id, region=aws_region)
    rule_name = None
    passed = False
    try:
        lt_id = harness.create_unencrypted()
        spec = _spec()
        log(f"===== Testing rule: {spec.rule_name} lt={lt_id} =====")
        compliance.wait_for_resource_discovered(
            resource_id=lt_id,
            resource_type="AWS::EC2::LaunchTemplate",
            timeout_seconds=300,
        )
        rule_name = config_mgr.put_managed_rule(spec, resource_id=lt_id)

        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=lt_id,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        harness.set_encrypted_default(True)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=lt_id,
            after_timestamp=change_ts,
            resource_type="AWS::EC2::LaunchTemplate",
        )
        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=lt_id,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed LT encryption cycle", style="green")
        passed = True
    finally:
        keep = os.environ.get("HARNESS_KEEP_ON_FAIL") == "1" and not passed
        if keep:
            log(f"KEEP on fail: rule={rule_name} lt={harness.template_id}", style="yellow")
        else:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as exc:
                    log(f"Cleanup warning: {exc}", style="yellow")
            harness.cleanup()
