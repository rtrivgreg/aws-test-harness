"""
First vertical slice – S3 managed rules.

By default this test runs only a small allowlist of rules so we can iterate
quickly without rate limits or unrelated CloudTrail/CloudFront/etc rules.

Set env ALLOW_ALL_S3_RULES=1 to run every rule returned by the catalog.
"""

from __future__ import annotations

import os
import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.s3_toggle import S3Toggle

# Keep this list tiny until the full cycle is proven green.
# Match against source_identifier (stable) or rule_name.
DEFAULT_ALLOWLIST = {
    "S3_BUCKET_VERSIONING_ENABLED",
    "s3-bucket-versioning-enabled",
    "RULE#s3-bucket-versioning-enabled",
}


def _is_allowed(spec: ManagedRuleSpec) -> bool:
    if os.environ.get("ALLOW_ALL_S3_RULES") == "1":
        return True
    return (
        spec.source_identifier in DEFAULT_ALLOWLIST
        or spec.rule_name in DEFAULT_ALLOWLIST
        or any(token in spec.rule_name for token in ("s3-bucket-versioning-enabled",))
    )


@pytest.mark.s3
@pytest.mark.slow
def test_s3_rule_compliance_cycle(
    s3_rules: list[ManagedRuleSpec],
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    s3_toggle: S3Toggle,
    s3_test_bucket: str,
) -> None:
    """
    Run the Put → NON_COMPLIANT → COMPLIANT → Delete cycle for allowed rules.
    """
    if not s3_rules:
        pytest.skip("No S3 rules available from the catalog")

    selected = [spec for spec in s3_rules if _is_allowed(spec)]
    if not selected:
        pytest.skip(
            "No allowlisted S3 rules found. "
            "Set ALLOW_ALL_S3_RULES=1 to run the full set, or extend DEFAULT_ALLOWLIST."
        )

    log(f"Running {len(selected)} allowlisted rule(s) (of {len(s3_rules)} from catalog)")

    failures: list[str] = []

    for spec in selected:
        rule_name = None
        try:
            log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")

            # a. PutConfigRule
            rule_name = config_mgr.put_managed_rule(spec)

            # c. Force NON_COMPLIANT
            s3_toggle.apply_strategy(spec.toggle_strategy, compliant=False)
            change_ts = time.time()

            # d. Start evaluation + poll
            config_mgr.start_evaluation(rule_name)
            config_mgr.wait_for_evaluation(rule_name, after_timestamp=change_ts)

            # e. Assert NON_COMPLIANT
            compliance.assert_resource_compliance(
                rule_name=rule_name,
                resource_id=s3_test_bucket,
                expected="NON_COMPLIANT",
                resource_type="AWS::S3::Bucket",
            )

            # f. Force COMPLIANT
            s3_toggle.apply_strategy(spec.toggle_strategy, compliant=True)
            change_ts = time.time()

            # g. Re-evaluate + assert COMPLIANT
            config_mgr.start_evaluation(rule_name)
            config_mgr.wait_for_evaluation(rule_name, after_timestamp=change_ts)
            compliance.assert_resource_compliance(
                rule_name=rule_name,
                resource_id=s3_test_bucket,
                expected="COMPLIANT",
                resource_type="AWS::S3::Bucket",
            )

            log(f"✓ {spec.rule_name} passed full compliance cycle", style="green")

        except Exception as exc:
            failures.append(f"{spec.rule_name}: {exc}")
            log(f"✗ {spec.rule_name} failed: {exc}", style="red")

        finally:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as cleanup_exc:
                    log(f"Cleanup warning for {rule_name}: {cleanup_exc}", style="yellow")

    if failures:
        pytest.fail(
            f"{len(failures)} S3 rule(s) failed the compliance cycle:\n"
            + "\n".join(failures)
        )
