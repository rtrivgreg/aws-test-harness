"""EFS_FILESYSTEM_CT_ENCRYPTED — unencrypted NC, encrypted C.

Change-triggered. Two throwaway file systems. No Terraform. No kmsKeyArns
(AWS-managed key on the encrypted FS is enough for C).
"""

from __future__ import annotations

import os
import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.efs_ct_toggle import EfsCtHarness


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="efs-filesystem-ct-encrypted",
        source_identifier="EFS_FILESYSTEM_CT_ENCRYPTED",
        input_parameters={},
        resource_types=["AWS::EFS::FileSystem"],
        toggle_strategy="efs_ct_encrypted",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> None:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}")
    log(f"EvaluationResults ({len(rows)}): {rows}")


@pytest.mark.efs
@pytest.mark.slow
def test_efs_filesystem_ct_encrypted(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    harness = EfsCtHarness(test_run_id=test_run_id, region=aws_region)
    rule_name = None
    passed = False
    try:
        unenc_id, enc_id = harness.create_pair()
        spec = _spec()
        log(f"===== Testing rule: {spec.rule_name} unenc={unenc_id} enc={enc_id} =====")
        compliance.wait_for_resource_discovered(
            resource_id=unenc_id, resource_type="AWS::EFS::FileSystem", timeout_seconds=300
        )
        compliance.wait_for_resource_discovered(
            resource_id=enc_id, resource_type="AWS::EFS::FileSystem", timeout_seconds=300
        )
        rule_name = config_mgr.put_managed_rule(spec)

        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=unenc_id,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=enc_id,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed unenc NC / enc C", style="green")
        passed = True
    finally:
        keep = os.environ.get("HARNESS_KEEP_ON_FAIL") == "1" and not passed
        if keep:
            log(
                f"KEEP on fail: rule={rule_name} unenc={harness.unenc_id} enc={harness.enc_id}",
                style="yellow",
            )
        else:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as exc:
                    log(f"Cleanup warning: {exc}", style="yellow")
            harness.cleanup()
