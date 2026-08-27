"""BACKUP_PLAN_MIN_FREQUENCY_AND_MIN_RETENTION_CHECK — 7-day vs 35-day retention."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Generator

import pytest

from harness.backup_toggle import BackupToggle
from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="backup-plan-min-frequency-and-min-retention-check",
        source_identifier="BACKUP_PLAN_MIN_FREQUENCY_AND_MIN_RETENTION_CHECK",
        input_parameters={
            "requiredFrequencyValue": "1",
            "requiredFrequencyUnit": "days",
            "requiredRetentionDays": "35",
        },
        resource_types=["AWS::Backup::BackupPlan"],
        toggle_strategy="backup_retention",
    )


@pytest.fixture(scope="session")
def backup_plan(
    test_run_id: str, aws_region: str, request: pytest.FixtureRequest
) -> Generator[dict, None, None]:
    tf_dir = Path(request.config.getoption("--terraform-dir"))
    env = os.environ.copy()
    env["TF_VAR_test_run_id"] = test_run_id
    env["TF_VAR_aws_region"] = aws_region
    env["TF_VAR_enable_backup_test"] = "true"
    log("Running terraform apply for Backup plan ...")
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
    plan_id = outputs.get("backup_plan_id", {}).get("value")
    vault = outputs.get("backup_vault_name", {}).get("value")
    if not plan_id:
        pytest.fail("terraform backup_plan_id is empty")
    log(f"Backup plan ready: {plan_id}")
    ComplianceChecker(region=aws_region).wait_for_resource_discovered(
        plan_id, "AWS::Backup::BackupPlan"
    )
    yield {"plan_id": plan_id, "vault_name": vault}


@pytest.mark.backup
@pytest.mark.slow
def test_backup_plan_min_retention(
    backup_plan: dict,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    plan_id = backup_plan["plan_id"]
    toggle = BackupToggle(
        plan_id=plan_id,
        vault_name=backup_plan["vault_name"],
        region=aws_region,
    )
    spec = _spec()
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        rule_name = config_mgr.put_managed_rule(spec)

        toggle.set_retention_days(7)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=plan_id,
            after_timestamp=change_ts,
            resource_type="AWS::Backup::BackupPlan",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        compliance.assert_resource_compliance(
            rule_name=rule_name,
            resource_id=plan_id,
            expected="NON_COMPLIANT",
            resource_type="AWS::Backup::BackupPlan",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )

        toggle.set_retention_days(35)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=plan_id,
            after_timestamp=change_ts,
            resource_type="AWS::Backup::BackupPlan",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        compliance.assert_resource_compliance(
            rule_name=rule_name,
            resource_id=plan_id,
            expected="COMPLIANT",
            resource_type="AWS::Backup::BackupPlan",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )
        log(f"{spec.rule_name} passed retention cycle", style="green")
    finally:
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
