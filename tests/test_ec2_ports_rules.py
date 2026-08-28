"""SG port restriction proofs.

RESTRICTED_INCOMING_TRAFFIC (restricted-common-ports) invokes in this
account but never publishes EvaluationResults. Parked after four live
misses on 2026-08-28. Same 3389 toggle is proven with
VPC_SG_PORT_RESTRICTION_CHECK.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Generator

import boto3
import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log

PORT = 3389


@pytest.fixture(scope="session")
def ec2_sg_ports(
    test_run_id: str, aws_region: str, request: pytest.FixtureRequest
) -> Generator[dict, None, None]:
    tf_dir = Path(request.config.getoption("--terraform-dir"))
    env = os.environ.copy()
    env["TF_VAR_test_run_id"] = test_run_id
    env["TF_VAR_aws_region"] = aws_region
    env["TF_VAR_enable_ec2_test"] = "true"
    log("Running terraform apply for EC2 ports fixture ...")
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
    sg = outputs.get("ec2_security_group_id", {}).get("value")
    assert sg, "ec2_security_group_id output empty"
    ComplianceChecker(region=aws_region).wait_for_resource_discovered(
        sg, "AWS::EC2::SecurityGroup"
    )
    yield {"security_group_id": sg}


def _nudge(ec2, sg: str, reason: str) -> None:
    ec2.create_tags(
        Resources=[sg],
        Tags=[
            {"Key": "harness-toggle-ts", "Value": str(int(time.time()))},
            {"Key": "harness-last-toggle", "Value": reason[:128]},
        ],
    )


def _open_rdp(ec2, sg: str) -> None:
    log(f"Opening TCP {PORT} 0.0.0.0/0 on {sg}")
    try:
        ec2.authorize_security_group_ingress(
            GroupId=sg,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort": PORT,
                "ToPort": PORT,
                "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "harness-nc"}],
            }],
        )
    except Exception as exc:
        log(f"authorize (may already exist): {exc}", style="yellow")
    _nudge(ec2, sg, "rdp-open")


def _close_rdp(ec2, sg: str) -> None:
    log(f"Revoking TCP {PORT} on {sg}")
    try:
        ec2.revoke_security_group_ingress(
            GroupId=sg,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort": PORT,
                "ToPort": PORT,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
            }],
        )
    except Exception as exc:
        log(f"revoke: {exc}", style="yellow")
    _nudge(ec2, sg, "rdp-closed")


@pytest.mark.ec2
@pytest.mark.slow
@pytest.mark.skip(
    reason=(
        "RESTRICTED_INCOMING_TRAFFIC invokes but publishes zero "
        "EvaluationResults in this account (four live misses 2026-08-28)."
    )
)
def test_restricted_common_ports(
    ec2_sg_ports: dict,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    pytest.skip("parked identifier")


@pytest.mark.ec2
@pytest.mark.slow
def test_vpc_sg_port_restriction(
    ec2_sg_ports: dict,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    sg = ec2_sg_ports["security_group_id"]
    ec2 = boto3.client("ec2", region_name=aws_region)
    spec = ManagedRuleSpec(
        rule_name="vpc-sg-port-restriction-check",
        source_identifier="VPC_SG_PORT_RESTRICTION_CHECK",
        input_parameters={
            "restrictPorts": "3389",
            "protocolType": "TCP",
            "excludeExternalSecurityGroups": "false",
            "ipType": "IPv4",
        },
        resource_types=["AWS::EC2::SecurityGroup"],
        toggle_strategy="ec2_rdp",
    )
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        rule_name = config_mgr.put_managed_rule(
            spec, maximum_execution_frequency="One_Hour"
        )

        _open_rdp(ec2, sg)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=sg, after_timestamp=change_ts,
            resource_type="AWS::EC2::SecurityGroup",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        config_mgr.dump_rule_debug(rule_name)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name, resource_id=sg, expected="NON_COMPLIANT",
            config_mgr=config_mgr, after_timestamp=None, timeout_seconds=600,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        _close_rdp(ec2, sg)
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=sg, after_timestamp=change_ts,
            resource_type="AWS::EC2::SecurityGroup",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name, resource_id=sg, expected="COMPLIANT",
            config_mgr=config_mgr, after_timestamp=eval_ts, timeout_seconds=600,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed port-restriction cycle", style="green")
    finally:
        try:
            _close_rdp(ec2, sg)
        except Exception:
            pass
        if rule_name:
            try:
                config_mgr.dump_rule_debug(rule_name)
            except Exception:
                pass
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
