"""EBS_LAST_BACKUP_RECOVERY_POINT_CREATED — no RP NC, on-demand job C.

Periodic. resourceId scopes to the throwaway volume.
Does not need Config to record AWS::Backup::RecoveryPoint.
"""

from __future__ import annotations

import os
import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.ebs_last_rp_toggle import EbsLastRpHarness


def _spec(volume_id: str) -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="ebs-last-backup-recovery-point-created",
        source_identifier="EBS_LAST_BACKUP_RECOVERY_POINT_CREATED",
        input_parameters={
            "resourceId": volume_id,
            "recoveryPointAgeValue": "1",
            "recoveryPointAgeUnit": "hours",
        },
        resource_types=["AWS::EC2::Volume"],
        toggle_strategy="ebs_last_rp",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> None:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}")
    log(f"EvaluationResults ({len(rows)}): {rows}")


@pytest.mark.ebs
@pytest.mark.backup
@pytest.mark.slow
def test_ebs_last_backup_recovery_point_created(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    harness = EbsLastRpHarness(test_run_id=test_run_id, region=aws_region)
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
        rule_name = config_mgr.put_managed_rule(
            spec, maximum_execution_frequency="TwentyFour_Hours"
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

        harness.start_and_wait()
        time.sleep(15)
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
        log(f"{spec.rule_name} passed no-RP NC / job-completed C", style="green")
        passed = True
    finally:
        keep = os.environ.get("HARNESS_KEEP_ON_FAIL") == "1" and not passed
        if keep:
            log(
                f"KEEP on fail: rule={rule_name} vol={harness.volume_id} rp={harness.rp_arn}",
                style="yellow",
            )
        else:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as exc:
                    log(f"Cleanup warning: {exc}", style="yellow")
            harness.cleanup()
