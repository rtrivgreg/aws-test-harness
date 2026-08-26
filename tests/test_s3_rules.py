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


def _run_one_leg(
    *,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    s3_toggle: S3Toggle,
    s3_test_bucket: str,
    rule_name: str,
    toggle_strategy: str,
    compliant: bool,
    expected: str,
    expected_versioning: str,
) -> None:
    """Toggle → wait for CI → evaluate → assert, with clocks after CI is ready."""
    s3_toggle.apply_strategy(toggle_strategy, compliant=compliant)
    change_ts = time.time()
    compliance.wait_for_config_item_after(
        resource_id=s3_test_bucket,
        after_timestamp=change_ts,
        resource_type="AWS::S3::Bucket",
        expected_versioning=expected_versioning,
    )
    # Critical: do not accept evaluations that finished before the CI was ready
    eval_ts = time.time()
    config_mgr.start_evaluation(rule_name)
    config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
    compliance.assert_resource_compliance(
        rule_name=rule_name,
        resource_id=s3_test_bucket,
        expected=expected,
        resource_type="AWS::S3::Bucket",
        config_mgr=config_mgr,
        after_timestamp=eval_ts,
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
    """Run the Put → NON_COMPLIANT → COMPLIANT → Delete cycle for allowed rules."""
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

            rule_name = config_mgr.put_managed_rule(spec)

            _run_one_leg(
                config_mgr=config_mgr,
                compliance=compliance,
                s3_toggle=s3_toggle,
                s3_test_bucket=s3_test_bucket,
                rule_name=rule_name,
                toggle_strategy=spec.toggle_strategy,
                compliant=False,
                expected="NON_COMPLIANT",
                expected_versioning="Suspended",
            )

            _run_one_leg(
                config_mgr=config_mgr,
                compliance=compliance,
                s3_toggle=s3_toggle,
                s3_test_bucket=s3_test_bucket,
                rule_name=rule_name,
                toggle_strategy=spec.toggle_strategy,
                compliant=True,
                expected="COMPLIANT",
                expected_versioning="Enabled",
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
