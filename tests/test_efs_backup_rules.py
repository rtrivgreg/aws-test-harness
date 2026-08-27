"""EFS_AUTOMATIC_BACKUPS_ENABLED — real toggle on one file system."""

from __future__ import annotations

import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.efs_toggle import EfsToggle


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="efs-automatic-backups-enabled",
        source_identifier="EFS_AUTOMATIC_BACKUPS_ENABLED",
        input_parameters={},
        resource_types=["AWS::EFS::FileSystem"],
        description="EFS automatic backups",
        toggle_strategy="efs_backups",
    )


@pytest.mark.efs
@pytest.mark.slow
def test_efs_automatic_backups_enabled(
    efs_filesystems: dict,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    fs_id = efs_filesystems["encrypted_id"]
    toggle = EfsToggle(file_system_id=fs_id, region=aws_region)
    spec = _spec()
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        rule_name = config_mgr.put_managed_rule(spec)

        toggle.set_automatic_backups(False)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=fs_id,
            after_timestamp=change_ts,
            resource_type="AWS::EFS::FileSystem",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        compliance.assert_resource_compliance(
            rule_name=rule_name,
            resource_id=fs_id,
            expected="NON_COMPLIANT",
            resource_type="AWS::EFS::FileSystem",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )

        toggle.set_automatic_backups(True)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=fs_id,
            after_timestamp=change_ts,
            resource_type="AWS::EFS::FileSystem",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        compliance.assert_resource_compliance(
            rule_name=rule_name,
            resource_id=fs_id,
            expected="COMPLIANT",
            resource_type="AWS::EFS::FileSystem",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )
        log(f"{spec.rule_name} passed backup toggle cycle", style="green")
    finally:
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
