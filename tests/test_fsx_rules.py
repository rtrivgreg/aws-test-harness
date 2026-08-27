"""FSX_OPENZFS_COPY_TAGS_ENABLED on a SINGLE_AZ_1 OpenZFS file system."""

from __future__ import annotations

import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.fsx_toggle import FsxToggle


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="fsx-openzfs-copy-tags-enabled",
        source_identifier="FSX_OPENZFS_COPY_TAGS_ENABLED",
        resource_types=["AWS::FSx::FileSystem"],
        toggle_strategy="fsx_copy_tags",
    )


@pytest.mark.fsx
@pytest.mark.slow
def test_fsx_openzfs_copy_tags(
    fsx_filesystem: dict,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    fs_id = fsx_filesystem["file_system_id"]
    toggle = FsxToggle(file_system_id=fs_id, region=aws_region)
    spec = _spec()
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        rule_name = config_mgr.put_managed_rule(spec)

        toggle.set_copy_tags(False)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=fs_id,
            after_timestamp=change_ts,
            resource_type="AWS::FSx::FileSystem",
            timeout_seconds=300,
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        compliance.assert_resource_compliance(
            rule_name=rule_name,
            resource_id=fs_id,
            expected="NON_COMPLIANT",
            resource_type="AWS::FSx::FileSystem",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )

        toggle.set_copy_tags(True)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=fs_id,
            after_timestamp=change_ts,
            resource_type="AWS::FSx::FileSystem",
            timeout_seconds=300,
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        compliance.assert_resource_compliance(
            rule_name=rule_name,
            resource_id=fs_id,
            expected="COMPLIANT",
            resource_type="AWS::FSx::FileSystem",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )
        log(f"{spec.rule_name} passed copy-tags cycle", style="green")
    finally:
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
