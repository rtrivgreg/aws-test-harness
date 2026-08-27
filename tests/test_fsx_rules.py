"""FSX_OPENZFS_COPY_TAGS_ENABLED on a SINGLE_AZ_1 OpenZFS file system."""

from __future__ import annotations

import time
from typing import Generator

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


@pytest.fixture(scope="session")
def fsx_filesystem(
    test_run_id: str, aws_region: str, request: pytest.FixtureRequest
) -> Generator[dict, None, None]:
    from pathlib import Path
    import os
    import json
    import subprocess

    tf_dir = Path(request.config.getoption("--terraform-dir"))
    env = os.environ.copy()
    env["TF_VAR_test_run_id"] = test_run_id
    env["TF_VAR_aws_region"] = aws_region
    env["TF_VAR_enable_fsx_test"] = "true"
    log("Running terraform apply for FSx OpenZFS ...")
    subprocess.run(["terraform", "init", "-input=false"], cwd=tf_dir, env=env, check=False)
    result = subprocess.run(
        ["terraform", "apply", "-auto-approve", "-input=false"],
        cwd=tf_dir, env=env, capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"terraform apply failed: {result.stderr}")
    out = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=tf_dir, env=env, capture_output=True, text=True, check=True,
    )
    outputs = json.loads(out.stdout)
    fs_id = outputs.get("fsx_file_system_id", {}).get("value")
    if not fs_id:
        pytest.fail("terraform fsx_file_system_id is empty")
    log(f"FSx file system ready: {fs_id}")
    ComplianceChecker(region=aws_region).wait_for_resource_discovered(
        fs_id, "AWS::FSx::FileSystem", timeout_seconds=600, poll_seconds=10
    )
    yield {"file_system_id": fs_id}


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
