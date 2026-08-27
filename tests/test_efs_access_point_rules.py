"""EFS access-point managed rules — two APs, no in-place toggle."""

from __future__ import annotations

import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log

RULES = [
    ManagedRuleSpec(
        rule_name="efs-access-point-enforce-root-directory",
        source_identifier="EFS_ACCESS_POINT_ENFORCE_ROOT_DIRECTORY",
        resource_types=["AWS::EFS::AccessPoint"],
        toggle_strategy="efs_two_ap",
    ),
    ManagedRuleSpec(
        rule_name="efs-access-point-enforce-user-identity",
        source_identifier="EFS_ACCESS_POINT_ENFORCE_USER_IDENTITY",
        resource_types=["AWS::EFS::AccessPoint"],
        toggle_strategy="efs_two_ap",
    ),
]


@pytest.mark.efs
@pytest.mark.slow
def test_efs_access_point_rules(
    efs_filesystems: dict,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
) -> None:
    nc_id = efs_filesystems.get("access_point_nc_id")
    c_id = efs_filesystems.get("access_point_c_id")
    if not nc_id or not c_id:
        pytest.fail("EFS access point outputs missing — terraform init/apply the updated module")

    failures: list[str] = []
    for spec in RULES:
        rule_name = None
        try:
            log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
            rule_name = config_mgr.put_managed_rule(spec)
            eval_ts = time.time()
            config_mgr.start_evaluation(rule_name)
            config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
            compliance.assert_resource_compliance(
                rule_name=rule_name,
                resource_id=nc_id,
                expected="NON_COMPLIANT",
                resource_type="AWS::EFS::AccessPoint",
                config_mgr=config_mgr,
                after_timestamp=eval_ts,
            )
            compliance.assert_resource_compliance(
                rule_name=rule_name,
                resource_id=c_id,
                expected="COMPLIANT",
                resource_type="AWS::EFS::AccessPoint",
                config_mgr=config_mgr,
                after_timestamp=eval_ts,
            )
            log(f"{spec.rule_name} passed two-AP cycle", style="green")
        except Exception as exc:
            failures.append(f"{spec.rule_name}: {exc}")
            log(f"{spec.rule_name} failed: {exc}", style="red")
        finally:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as cleanup_exc:
                    log(f"Cleanup warning: {cleanup_exc}", style="yellow")
    if failures:
        pytest.fail("\n".join(failures))
