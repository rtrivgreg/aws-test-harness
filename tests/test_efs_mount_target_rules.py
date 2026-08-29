"""EFS_MOUNT_TARGET_PUBLIC_ACCESSIBLE — public-subnet MT NC, private-subnet MT C.

Periodic. Two throwaway file systems. No Terraform. Does not change
MapPublicIpOnLaunch on existing subnets.
"""

from __future__ import annotations

import os
import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.efs_mt_toggle import EfsMountTargetHarness


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="efs-mount-target-public-accessible",
        source_identifier="EFS_MOUNT_TARGET_PUBLIC_ACCESSIBLE",
        input_parameters={},
        resource_types=["AWS::EFS::FileSystem"],
        toggle_strategy="efs_mt_public",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> None:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}")
    log(f"EvaluationResults ({len(rows)}): {rows}")


@pytest.mark.efs
@pytest.mark.slow
def test_efs_mount_target_public_accessible(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    harness = EfsMountTargetHarness(test_run_id=test_run_id, region=aws_region)
    rule_name = None
    passed = False
    try:
        nc_id, c_id = harness.create_pair()
        spec = _spec()
        log(
            f"===== Testing rule: {spec.rule_name} "
            f"nc={nc_id}@{harness.public_subnet_id} "
            f"c={c_id}@{harness.private_subnet_id} ====="
        )
        compliance.wait_for_resource_discovered(
            resource_id=nc_id, resource_type="AWS::EFS::FileSystem", timeout_seconds=300
        )
        compliance.wait_for_resource_discovered(
            resource_id=c_id, resource_type="AWS::EFS::FileSystem", timeout_seconds=300
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
            resource_id=nc_id,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=c_id,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed public-MT NC / private-MT C", style="green")
        passed = True
    finally:
        keep = os.environ.get("HARNESS_KEEP_ON_FAIL") == "1" and not passed
        if keep:
            log(
                f"KEEP on fail: rule={rule_name} nc={harness.nc_fs_id} c={harness.c_fs_id}",
                style="yellow",
            )
        else:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as exc:
                    log(f"Cleanup warning: {exc}", style="yellow")
            harness.cleanup()
