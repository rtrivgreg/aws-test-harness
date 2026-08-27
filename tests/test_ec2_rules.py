"""EC2_IMDSV2_CHECK — HttpTokens optional vs required."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Generator

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.ec2_toggle import Ec2Toggle


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="ec2-imdsv2-check",
        source_identifier="EC2_IMDSV2_CHECK",
        resource_types=["AWS::EC2::Instance"],
        toggle_strategy="ec2_imdsv2",
    )


@pytest.fixture(scope="session")
def ec2_instance(
    test_run_id: str, aws_region: str, request: pytest.FixtureRequest
) -> Generator[dict, None, None]:
    tf_dir = Path(request.config.getoption("--terraform-dir"))
    env = os.environ.copy()
    env["TF_VAR_test_run_id"] = test_run_id
    env["TF_VAR_aws_region"] = aws_region
    env["TF_VAR_enable_ec2_test"] = "true"
    log("Running terraform apply for EC2 test instance ...")
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
    iid = outputs.get("ec2_instance_id", {}).get("value")
    if not iid:
        pytest.fail("terraform ec2_instance_id is empty — enable_ec2_test module not wired?")
    log(f"EC2 instance ready: {iid}")
    ComplianceChecker(region=aws_region).wait_for_resource_discovered(
        iid, "AWS::EC2::Instance"
    )
    yield {"instance_id": iid}


@pytest.mark.ec2
@pytest.mark.slow
def test_ec2_imdsv2_check(
    ec2_instance: dict,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    iid = ec2_instance["instance_id"]
    toggle = Ec2Toggle(instance_id=iid, region=aws_region)
    spec = _spec()
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        rule_name = config_mgr.put_managed_rule(spec)

        toggle.set_imdsv2_required(False)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=iid,
            after_timestamp=change_ts,
            resource_type="AWS::EC2::Instance",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        compliance.assert_resource_compliance(
            rule_name=rule_name,
            resource_id=iid,
            expected="NON_COMPLIANT",
            resource_type="AWS::EC2::Instance",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )

        toggle.set_imdsv2_required(True)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=iid,
            after_timestamp=change_ts,
            resource_type="AWS::EC2::Instance",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        compliance.assert_resource_compliance(
            rule_name=rule_name,
            resource_id=iid,
            expected="COMPLIANT",
            resource_type="AWS::EC2::Instance",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )
        log(f"{spec.rule_name} passed IMDSv2 cycle", style="green")
    finally:
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
