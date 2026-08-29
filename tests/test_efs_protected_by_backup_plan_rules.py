"""EFS_RESOURCES_PROTECTED_BY_BACKUP_PLAN — off-plan NC, on-plan C.

Periodic. resourceId is a valid optional parameter on this identifier.
Throwaway EFS + backup selection. No Terraform.
EBS twin of this identifier parked INSUFFICIENT_DATA on this recorder.
"""

from __future__ import annotations

import os
import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.efs_plan_toggle import EfsPlanProtectHarness


def _spec(fs_id: str) -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="efs-resources-protected-by-backup-plan",
        source_identifier="EFS_RESOURCES_PROTECTED_BY_BACKUP_PLAN",
        input_parameters={"resourceId": fs_id},
        resource_types=["AWS::EFS::FileSystem"],
        toggle_strategy="efs_protected_by_plan",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> None:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}")
    log(f"EvaluationResults ({len(rows)}): {rows}")


@pytest.mark.efs
@pytest.mark.backup
@pytest.mark.slow
def test_efs_resources_protected_by_backup_plan(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    harness = EfsPlanProtectHarness(
        test_run_id=test_run_id, region=aws_region, prefix="cfg-efs-prot"
    )
    rule_name = None
    passed = False
    try:
        fs_id = harness.create_filesystem()
        spec = _spec(fs_id)
        log(f"===== Testing rule: {spec.rule_name} fs={fs_id} =====")
        compliance.wait_for_resource_discovered(
            resource_id=fs_id,
            resource_type="AWS::EFS::FileSystem",
            timeout_seconds=300,
        )
        rule_name = config_mgr.put_managed_rule(
            spec, maximum_execution_frequency="TwentyFour_Hours"
        )

        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=fs_id,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        harness.protect()
        time.sleep(20)
        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=fs_id,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed off-plan NC / on-plan C", style="green")
        passed = True
    finally:
        keep = os.environ.get("HARNESS_KEEP_ON_FAIL") == "1" and not passed
        if keep:
            log(
                f"KEEP on fail: rule={rule_name} fs={harness.fs_id} plan={harness.plan_id}",
                style="yellow",
            )
        else:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as exc:
                    log(f"Cleanup warning: {exc}", style="yellow")
            harness.cleanup()
