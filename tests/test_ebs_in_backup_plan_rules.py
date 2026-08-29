"""EBS_IN_BACKUP_PLAN — off-plan NC, on-plan C.

Periodic. No input parameters, so Config evaluates every recorded volume.
Wait until the throwaway volume itself appears in EvaluationResults.
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


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="ebs-in-backup-plan",
        source_identifier="EBS_IN_BACKUP_PLAN",
        input_parameters={},
        resource_types=["AWS::EC2::Volume"],
        toggle_strategy="ebs_in_backup_plan",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> None:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}")
    log(f"EvaluationResults ({len(rows)}): {rows}")
    return rows


def _eval_until_volume(
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    rule_name: str,
    volume_id: str,
    expected: str,
    attempts: int = 3,
):
    last = None
    for i in range(1, attempts + 1):
        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        rows = _dump(config_mgr, compliance, rule_name)
        ids = [r.split(":", 1)[0] for r in rows]
        if volume_id in ids:
            return compliance.wait_for_resource_result(
                rule_name=rule_name,
                resource_id=volume_id,
                expected=expected,
                config_mgr=config_mgr,
                after_timestamp=eval_ts,
                timeout_seconds=120,
            )
        log(
            f"Attempt {i}: harness volume {volume_id} not in results {ids}; settle 30s",
            style="yellow",
        )
        time.sleep(30)
        last = rows
    raise AssertionError(
        f"{volume_id} never appeared under {rule_name}. Last results={last}"
    )


@pytest.mark.ebs
@pytest.mark.backup
@pytest.mark.slow
def test_ebs_in_backup_plan(
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
        spec = _spec()
        log(f"===== Testing rule: {spec.rule_name} volume={volume_id} =====")
        compliance.wait_for_resource_discovered(
            resource_id=volume_id,
            resource_type="AWS::EC2::Volume",
            timeout_seconds=300,
        )
        time.sleep(20)
        rule_name = config_mgr.put_managed_rule(
            spec, maximum_execution_frequency="TwentyFour_Hours"
        )

        nc = _eval_until_volume(
            config_mgr, compliance, rule_name, volume_id, "NON_COMPLIANT"
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        harness.protect()
        time.sleep(20)
        c = _eval_until_volume(
            config_mgr, compliance, rule_name, volume_id, "COMPLIANT"
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed off-plan NC / on-plan C", style="green")
        passed = True
    finally:
        keep = os.environ.get("HARNESS_KEEP_ON_FAIL") == "1" and not passed
        if keep:
            log(
                f"KEEP on fail: rule={rule_name} volume={harness.volume_id} plan={harness.plan_id}",
                style="yellow",
            )
        else:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as exc:
                    log(f"Cleanup warning: {exc}", style="yellow")
            harness.cleanup()
