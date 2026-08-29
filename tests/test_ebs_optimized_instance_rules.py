"""EBS_OPTIMIZED_INSTANCE — optional type EbsOptimized=false NC, t3.nano C.

Change-triggered. Two throwaway instances. No Terraform.
Do not use the harness runner instance.
"""

from __future__ import annotations

import os
import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.ebs_opt_toggle import EbsOptimizedHarness


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="ebs-optimized-instance",
        source_identifier="EBS_OPTIMIZED_INSTANCE",
        input_parameters={},
        resource_types=["AWS::EC2::Instance"],
        toggle_strategy="ebs_optimized",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> None:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}")
    log(f"EvaluationResults ({len(rows)}): {rows}")


@pytest.mark.ebs
@pytest.mark.slow
def test_ebs_optimized_instance(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    harness = EbsOptimizedHarness(test_run_id=test_run_id, region=aws_region)
    rule_name = None
    passed = False
    try:
        nc_id, c_id = harness.create_pair()
        spec = _spec()
        log(
            f"===== Testing rule: {spec.rule_name} "
            f"nc={nc_id}/{harness.optional_type} c={c_id}/t3.nano ====="
        )
        compliance.wait_for_resource_discovered(
            resource_id=nc_id, resource_type="AWS::EC2::Instance", timeout_seconds=300
        )
        compliance.wait_for_resource_discovered(
            resource_id=c_id, resource_type="AWS::EC2::Instance", timeout_seconds=300
        )
        rule_name = config_mgr.put_managed_rule(spec)

        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
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
        log(f"{spec.rule_name} passed optional-type NC / t3.nano C", style="green")
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
