"""EFS_ENCRYPTED_CHECK — two file systems, encryption set at create time."""

from __future__ import annotations

import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="efs-encrypted-check",
        source_identifier="EFS_ENCRYPTED_CHECK",
        input_parameters={},
        resource_types=["AWS::EFS::FileSystem"],
        description="EFS encryption at rest",
        toggle_strategy="efs_two_fs",
    )


@pytest.mark.efs
@pytest.mark.slow
def test_efs_encrypted_check(
    efs_filesystems: dict,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
) -> None:
    unenc = efs_filesystems["unencrypted_id"]
    enc = efs_filesystems["encrypted_id"]
    spec = _spec()
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        log(f"EFS unenc={unenc} enc={enc}")
        rule_name = config_mgr.put_managed_rule(spec)
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        compliance.assert_resource_compliance(
            rule_name=rule_name,
            resource_id=unenc,
            expected="NON_COMPLIANT",
            resource_type="AWS::EFS::FileSystem",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )
        compliance.assert_resource_compliance(
            rule_name=rule_name,
            resource_id=enc,
            expected="COMPLIANT",
            resource_type="AWS::EFS::FileSystem",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )
        log(f"{spec.rule_name} passed two-FS cycle", style="green")
    finally:
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
