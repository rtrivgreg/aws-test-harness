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
    assert plan_id, "terraform backup_plan_id is empty"
    assert vault, "terraform backup_vault_name is empty"
    log(f"Backup plan ready: {plan_id}")
    ComplianceChecker(region=aws_region).wait_for_resource_discovered(
        plan_id, "AWS::Backup::BackupPlan"
    )
    yield {"plan_id": plan_id, "vault_name": vault}


def _eval_type(
    compliance: ComplianceChecker,
    config_mgr: ConfigRuleManager,
    rule_name: str,
    resource_id: str,
    after_ts: float,
) -> str:
    result = compliance.get_result_for_resource(
        rule_name=rule_name,
        resource_id=resource_id,
        resource_type="AWS::Backup::BackupPlan",
        config_mgr=config_mgr,
        after_timestamp=after_ts,
    )
    assert result is not None, (
        f"No evaluation result for {resource_id} under {rule_name}"
    )
    ctype = result.get("ComplianceType")
    assert ctype in {"COMPLIANT", "NON_COMPLIANT", "NOT_APPLICABLE", "INSUFFICIENT_DATA"}, (
        f"Unexpected ComplianceType {ctype!r}"
    )
    return ctype


@pytest.mark.backup
@pytest.mark.slow
def test_backup_plan_min_retention(
    backup_plan: dict,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    plan_id = backup_plan["plan_id"]
    vault = backup_plan["vault_name"]
    assert plan_id.startswith("")  # plan ids are opaque; non-empty already checked
    assert vault.startswith("cfg-backup-vault-"), vault

    toggle = BackupToggle(plan_id=plan_id, vault_name=vault, region=aws_region)
    spec = _spec()
    assert spec.source_identifier == "BACKUP_PLAN_MIN_FREQUENCY_AND_MIN_RETENTION_CHECK"
    assert spec.input_parameters["requiredRetentionDays"] == "35"

    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        rule_name = config_mgr.put_managed_rule(spec)
        assert rule_name, "PutConfigRule did not return a rule name"
        assert "backup-plan-min-frequency" in rule_name

        # --- NON_COMPLIANT: retention 7 < required 35 ---
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
        actual_nc = _eval_type(compliance, config_mgr, rule_name, plan_id, eval_ts)
        assert actual_nc == "NON_COMPLIANT", (
            f"Expected NON_COMPLIANT with 7-day retention vs required 35; got {actual_nc}"
        )
        log(f"{plan_id} is NON_COMPLIANT under {rule_name}", style="green")

        # --- COMPLIANT: retention 35 meets required 35 ---
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
        actual_c = _eval_type(compliance, config_mgr, rule_name, plan_id, eval_ts)
        assert actual_c == "COMPLIANT", (
            f"Expected COMPLIANT with 35-day retention vs required 35; got {actual_c}"
        )
        log(f"{plan_id} is COMPLIANT under {rule_name}", style="green")
        log(f"{spec.rule_name} passed retention cycle", style="green")
    finally:
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
