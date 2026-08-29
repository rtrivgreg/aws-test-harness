"""EBS_RESOURCES_PROTECTED_BY_BACKUP_PLAN — volume off-plan then on-plan.

Periodic rule. Do not set Scope.ComplianceResourceId (change-triggered only).
Filter with input resourceId. Dump results and keep rule+volume on failure.
"""

from __future__ import annotations

import os
import time

import pytest

from harness.backup_toggle import PlanProtectHarness
from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log


def _spec(volume_id: str) -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="ebs-resources-protected-by-backup-plan",
        source_identifier="EBS_RESOURCES_PROTECTED_BY_BACKUP_PLAN",
        input_parameters={"resourceId": volume_id},
        resource_types=["AWS::EC2::Volume"],
        toggle_strategy="ebs_backup_plan",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> None:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(
            f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}"
        )
    log(f"EvaluationResults ({len(rows)}): {rows}")


@pytest.mark.ebs
@pytest.mark.backup
@pytest.mark.slow
def test_ebs_resources_protected_by_backup_plan(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    harness = PlanProtectHarness(test_run_id=test_run_id, region=aws_region)
    rule_name = None
    passed = False
    try:
        volume_id = harness.create_volume()
        spec = _spec(volume_id)
        log(f"===== Testing rule: {spec.rule_name} volume={volume_id} =====")
        compliance.wait_for_resource_discovered(
            resource_id=volume_id,
            resource_type="AWS::EC2::Volume",
            timeout_seconds=300,
        )

        # Periodic rule: frequency required. Do not pass resource_id into Scope.
        rule_name = config_mgr.put_managed_rule(
            spec,
            maximum_execution_frequency="TwentyFour_Hours",
        )

        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=volume_id,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"
        log(f"{volume_id} NON_COMPLIANT off-plan", style="green")

        harness.protect()
        time.sleep(20)
        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=volume_id,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{volume_id} COMPLIANT on-plan", style="green")
        log(f"{spec.rule_name} passed plan-protect cycle", style="green")
        passed = True
    finally:
        keep = os.environ.get("HARNESS_KEEP_ON_FAIL") == "1" and not passed
        if keep:
            log(
                f"KEEP on fail: rule={rule_name} volume={harness.volume_id}",
                style="yellow",
            )
        else:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as exc:
                    log(f"Cleanup warning: {exc}", style="yellow")
            harness.cleanup()
