"""BACKUP_RECOVERY_POINT_ENCRYPTED — unencrypted EBS RP vs encrypted EBS RP.

No Terraform apply. Throwaway volumes + vault, deleted in finally.
"""

from __future__ import annotations

import time

import pytest

from harness.backup_toggle import RecoveryPointHarness
from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="backup-recovery-point-encrypted",
        source_identifier="BACKUP_RECOVERY_POINT_ENCRYPTED",
        input_parameters={},
        resource_types=["AWS::Backup::RecoveryPoint"],
        toggle_strategy="backup_recovery_point_encrypted",
    )


@pytest.mark.backup
@pytest.mark.slow
def test_backup_recovery_point_encrypted(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    harness = RecoveryPointHarness(test_run_id=test_run_id, region=aws_region)
    spec = _spec()
    rule_name = None
    provisioned = False
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        resources = harness.provision()
        provisioned = True
        nc_arn = resources["nc_rp_arn"]
        c_arn = resources["c_rp_arn"]

        # Config resourceId for RecoveryPoint is the ARN.
        compliance.wait_for_resource_discovered(
            resource_id=nc_arn,
            resource_type="AWS::Backup::RecoveryPoint",
            timeout_seconds=600,
        )
        rule_name = config_mgr.put_managed_rule(spec, resource_id=nc_arn)
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        nc_hits = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=nc_arn,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=600,
        )
        assert nc_hits[0]["ComplianceType"] == "NON_COMPLIANT"
        log(f"{nc_arn} is NON_COMPLIANT under {rule_name}", style="green")

        compliance.wait_for_resource_discovered(
            resource_id=c_arn,
            resource_type="AWS::Backup::RecoveryPoint",
            timeout_seconds=600,
        )
        rule_name = config_mgr.put_managed_rule(spec, resource_id=c_arn)
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        c_hits = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=c_arn,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=600,
        )
        assert c_hits[0]["ComplianceType"] == "COMPLIANT"
        log(f"{c_arn} is COMPLIANT under {rule_name}", style="green")
        log(f"{spec.rule_name} passed encrypted-RP cycle", style="green")
    finally:
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
        if provisioned:
            harness.cleanup()
