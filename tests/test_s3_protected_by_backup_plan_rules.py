"""S3_RESOURCES_PROTECTED_BY_BACKUP_PLAN — live bucket off-plan NC, on-plan C.

Periodic. Uses S3_TEST_BUCKET. Does not apply Terraform or delete the bucket.
"""

from __future__ import annotations

import os
import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.s3_plan_toggle import S3PlanProtectHarness


def _spec(bucket: str) -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3-resources-protected-by-backup-plan",
        source_identifier="S3_RESOURCES_PROTECTED_BY_BACKUP_PLAN",
        input_parameters={"resourceId": bucket},
        resource_types=["AWS::S3::Bucket"],
        toggle_strategy="s3_protected_by_plan",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> None:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}")
    log(f"EvaluationResults ({len(rows)}): {rows}")


@pytest.mark.s3
@pytest.mark.backup
@pytest.mark.slow
def test_s3_resources_protected_by_backup_plan(
    s3_test_bucket: str,
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    harness = S3PlanProtectHarness(
        test_run_id=test_run_id, bucket_name=s3_test_bucket, region=aws_region
    )
    rule_name = None
    passed = False
    try:
        spec = _spec(s3_test_bucket)
        log(f"===== Testing rule: {spec.rule_name} bucket={s3_test_bucket} =====")
        rule_name = config_mgr.put_managed_rule(
            spec, maximum_execution_frequency="TwentyFour_Hours"
        )

        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=s3_test_bucket,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        harness.protect()
        time.sleep(20)
        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=s3_test_bucket,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed off-plan NC / on-plan C", style="green")
        passed = True
    finally:
        keep = os.environ.get("HARNESS_KEEP_ON_FAIL") == "1" and not passed
        if keep:
            log(
                f"KEEP on fail: rule={rule_name} plan={harness.plan_id} bucket={s3_test_bucket}",
                style="yellow",
            )
        else:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as exc:
                    log(f"Cleanup warning: {exc}", style="yellow")
            harness.cleanup()
