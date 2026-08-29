"""EC2_EBS_ENCRYPTION_BY_DEFAULT — off NC, on C.

Periodic account rule. Queries live GetEbsEncryptionByDefault, not a CI.
Restore enabled=True in finally.
"""

from __future__ import annotations

import os
import time

import boto3
import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.ebs_enc_default import EbsEncryptionByDefault


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="ec2-ebs-encryption-by-default",
        source_identifier="EC2_EBS_ENCRYPTION_BY_DEFAULT",
        input_parameters={},
        resource_types=["AWS::::Account"],
        toggle_strategy="ebs_enc_default",
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
def test_ec2_ebs_encryption_by_default(
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    account = boto3.client("sts").get_caller_identity()["Account"]
    toggle = EbsEncryptionByDefault(region=aws_region)
    spec = _spec()
    rule_name = None
    passed = False
    try:
        log(f"===== Testing rule: {spec.rule_name} account={account} =====")
        log(f"Current encryption-by-default={toggle.enabled()}")
        rule_name = config_mgr.put_managed_rule(
            spec, maximum_execution_frequency="TwentyFour_Hours"
        )

        toggle.set(False)
        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=account,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        toggle.set(True)
        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=account,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed encryption-by-default cycle", style="green")
        passed = True
    finally:
        try:
            toggle.set(True)
        except Exception as exc:
            log(f"restore encryption-by-default: {exc}", style="yellow")
        keep = os.environ.get("HARNESS_KEEP_ON_FAIL") == "1" and not passed
        if keep:
            log(f"KEEP on fail: rule={rule_name}", style="yellow")
        elif rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
