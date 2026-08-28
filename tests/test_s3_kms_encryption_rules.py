"""S3_DEFAULT_ENCRYPTION_KMS — AES256 vs aws:kms.

S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED cannot prove NON_COMPLIANT on
modern buckets (SSE-S3 is implicit). This rule can: AES256 is NC, KMS is C.
"""

from __future__ import annotations

import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.s3_toggle import S3Toggle


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3-default-encryption-kms",
        source_identifier="S3_DEFAULT_ENCRYPTION_KMS",
        resource_types=["AWS::S3::Bucket"],
        toggle_strategy="s3_kms_encryption",
    )


@pytest.mark.s3
@pytest.mark.slow
def test_s3_default_encryption_kms(
    s3_test_bucket: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    s3_toggle: S3Toggle,
) -> None:
    spec = _spec()
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        rule_name = config_mgr.put_managed_rule(spec)

        s3_toggle.make_kms_encryption_noncompliant()
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=s3_test_bucket,
            after_timestamp=change_ts,
            resource_type="AWS::S3::Bucket",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=s3_test_bucket,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        s3_toggle.make_kms_encryption_compliant()
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=s3_test_bucket,
            after_timestamp=change_ts,
            resource_type="AWS::S3::Bucket",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=s3_test_bucket,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed KMS-encryption cycle", style="green")
    finally:
        try:
            s3_toggle.make_encryption_compliant()
        except Exception as exc:
            log(f"Cleanup toggle: {exc}", style="yellow")
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
