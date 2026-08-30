"""S3EXPRESS_DIR_BUCKET_LIFECYCLE_RULES_CHECK — no lifecycle NC, ExpirationInDays=7 C.

Throwaway directory bucket. No Terraform. Park if Config never discovers
AWS::S3Express::DirectoryBucket (same class of miss as FSx OpenZFS).
"""

from __future__ import annotations

import os
import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.s3express_toggle import EXPIRATION_DAYS, S3ExpressLifecycleHarness

RESOURCE_TYPE = "AWS::S3Express::DirectoryBucket"


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3express-dir-bucket-lifecycle-rules-check",
        source_identifier="S3EXPRESS_DIR_BUCKET_LIFECYCLE_RULES_CHECK",
        input_parameters={"targetExpirationDays": str(EXPIRATION_DAYS)},
        resource_types=[RESOURCE_TYPE],
        toggle_strategy="s3express_lifecycle",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> list[str]:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}")
    log(f"EvaluationResults ({len(rows)}): {rows}")
    return rows


@pytest.mark.s3
@pytest.mark.slow
def test_s3express_dir_bucket_lifecycle_rules_check(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    harness = S3ExpressLifecycleHarness(test_run_id=test_run_id, region=aws_region)
    rule_name = None
    passed = False
    try:
        bucket = harness.create()
        spec = _spec()
        log(f"===== Testing rule: {spec.rule_name} bucket={bucket} az={harness.az_id} =====")
        try:
            compliance.wait_for_resource_discovered(
                resource_id=bucket,
                resource_type=RESOURCE_TYPE,
                timeout_seconds=420,
                poll_seconds=15,
            )
        except TimeoutError as exc:
            raise AssertionError(
                f"Park S3EXPRESS_DIR_BUCKET_LIFECYCLE_RULES_CHECK — Config never "
                f"discovered {RESOURCE_TYPE} {bucket}. {exc}"
            ) from exc

        rule_name = config_mgr.put_managed_rule(spec)

        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        rows = _dump(config_mgr, compliance, rule_name)
        if not rows:
            raise AssertionError(
                "Empty EvaluationResults — park S3EXPRESS_DIR_BUCKET_LIFECYCLE_RULES_CHECK"
            )

        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=bucket,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        harness.put_expiration(EXPIRATION_DAYS)
        time.sleep(15)
        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=bucket,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed no-lifecycle NC / ExpirationInDays={EXPIRATION_DAYS} C", style="green")
        passed = True
    finally:
        keep = os.environ.get("HARNESS_KEEP_ON_FAIL") == "1" and not passed
        if keep:
            log(
                f"KEEP on fail: rule={rule_name} bucket={harness.bucket_name}",
                style="yellow",
            )
        else:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as exc:
                    log(f"Cleanup warning: {exc}", style="yellow")
            harness.cleanup()
