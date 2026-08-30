"""EC2_SPOT_FLEET_REQUEST_CT_ENCRYPTION_AT_REST — Encrypted=false NC, true C.

Launch specifications only. TargetCapacity=0. No Terraform.
Park if Config never discovers AWS::EC2::SpotFleet.
"""

from __future__ import annotations

import os
import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.spot_fleet_toggle import SpotFleetEncryptHarness

RESOURCE_TYPE = "AWS::EC2::SpotFleet"


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="ec2-spot-fleet-request-ct-encryption-at-rest",
        source_identifier="EC2_SPOT_FLEET_REQUEST_CT_ENCRYPTION_AT_REST",
        input_parameters={},
        resource_types=[RESOURCE_TYPE],
        toggle_strategy="spot_fleet_ebs_encrypted",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> list[str]:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}")
    log(f"EvaluationResults ({len(rows)}): {rows}")
    return rows


@pytest.mark.ec2
@pytest.mark.ebs
@pytest.mark.slow
def test_ec2_spot_fleet_request_ct_encryption_at_rest(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    harness = SpotFleetEncryptHarness(test_run_id=test_run_id, region=aws_region)
    rule_name = None
    passed = False
    try:
        nc_id, c_id = harness.create_pair()
        spec = _spec()
        log(f"===== Testing rule: {spec.rule_name} nc={nc_id} c={c_id} =====")
        try:
            compliance.wait_for_resource_discovered(
                resource_id=nc_id, resource_type=RESOURCE_TYPE, timeout_seconds=420, poll_seconds=15
            )
            compliance.wait_for_resource_discovered(
                resource_id=c_id, resource_type=RESOURCE_TYPE, timeout_seconds=420, poll_seconds=15
            )
        except TimeoutError as exc:
            raise AssertionError(
                f"Park EC2_SPOT_FLEET_REQUEST_CT_ENCRYPTION_AT_REST — Config never "
                f"discovered {RESOURCE_TYPE}. {exc}"
            ) from exc

        rule_name = config_mgr.put_managed_rule(spec)
        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        rows = _dump(config_mgr, compliance, rule_name)
        if not rows:
            raise AssertionError(
                "Empty EvaluationResults — park EC2_SPOT_FLEET_REQUEST_CT_ENCRYPTION_AT_REST"
            )

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
        log(f"{spec.rule_name} passed Encrypted=false NC / Encrypted=true C", style="green")
        passed = True
    finally:
        keep = os.environ.get("HARNESS_KEEP_ON_FAIL") == "1" and not passed
        if keep:
            log(
                f"KEEP on fail: rule={rule_name} nc={harness.nc_id} c={harness.c_id}",
                style="yellow",
            )
        else:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as exc:
                    log(f"Cleanup warning: {exc}", style="yellow")
            harness.cleanup()
