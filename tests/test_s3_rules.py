"""
First vertical slice – S3 managed rules.

Default allowlist covers versioning + lifecycle rules. Set ALLOW_ALL_S3_RULES=1
to run every rule returned by the catalog (not recommended until strategies exist).
"""

from __future__ import annotations

import os
import time
from typing import Optional

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.s3_toggle import S3Toggle

DEFAULT_ALLOWLIST = {
    # Versioning
    "S3_BUCKET_VERSIONING_ENABLED",
    "s3-bucket-versioning-enabled",
    "RULE#s3-bucket-versioning-enabled",
    # Lifecycle (general)
    "S3_LIFECYCLE_POLICY_CHECK",
    "s3-lifecycle-policy-check",
    "RULE#s3-lifecycle-policy-check",
    # Lifecycle on versioned buckets
    "S3_VERSION_LIFECYCLE_POLICY_CHECK",
    "s3-version-lifecycle-policy-check",
    "RULE#s3-version-lifecycle-policy-check",
}

# source_identifier → (toggle_strategy, expected_versioning NC, expected_lifecycle NC,
#                      expected_versioning C, expected_lifecycle C)
# expected_* is None when that attribute is not asserted on the CI wait.
RULE_PROFILES = {
    "S3_BUCKET_VERSIONING_ENABLED": {
        "strategy": "s3_versioning",
        "nc_versioning": "Suspended",
        "nc_lifecycle": None,
        "c_versioning": "Enabled",
        "c_lifecycle": None,
    },
    "S3_LIFECYCLE_POLICY_CHECK": {
        "strategy": "s3_lifecycle",
        "nc_versioning": None,
        "nc_lifecycle": False,
        "c_versioning": None,
        "c_lifecycle": True,
    },
    "S3_VERSION_LIFECYCLE_POLICY_CHECK": {
        "strategy": "s3_version_lifecycle",
        "nc_versioning": "Enabled",
        "nc_lifecycle": False,
        "c_versioning": "Enabled",
        "c_lifecycle": True,
    },
}


def _is_allowed(spec: ManagedRuleSpec) -> bool:
    if os.environ.get("ALLOW_ALL_S3_RULES") == "1":
        return True
    tokens = (
        "s3-bucket-versioning-enabled",
        "s3-lifecycle-policy-check",
        "s3-version-lifecycle-policy-check",
    )
    return (
        spec.source_identifier in DEFAULT_ALLOWLIST
        or spec.rule_name in DEFAULT_ALLOWLIST
        or any(t in spec.rule_name for t in tokens)
    )


def _profile_for(spec: ManagedRuleSpec) -> dict:
    if spec.source_identifier in RULE_PROFILES:
        return RULE_PROFILES[spec.source_identifier]
    # Fallback: treat as versioning
    return RULE_PROFILES["S3_BUCKET_VERSIONING_ENABLED"]


def _run_one_leg(
    *,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    s3_toggle: S3Toggle,
    s3_test_bucket: str,
    rule_name: str,
    strategy: str,
    compliant: bool,
    expected: str,
    expected_versioning: Optional[str],
    expected_lifecycle: Optional[bool],
) -> None:
    s3_toggle.apply_strategy(strategy, compliant=compliant)
    change_ts = time.time()
    compliance.wait_for_config_item_after(
        resource_id=s3_test_bucket,
        after_timestamp=change_ts,
        resource_type="AWS::S3::Bucket",
        expected_versioning=expected_versioning,
        expected_lifecycle=expected_lifecycle,
    )
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
        profile = _profile_for(spec)
        try:
            log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
            log(f"Using strategy={profile['strategy']}")

            rule_name = config_mgr.put_managed_rule(spec)

            _run_one_leg(
                config_mgr=config_mgr,
                compliance=compliance,
                s3_toggle=s3_toggle,
                s3_test_bucket=s3_test_bucket,
                rule_name=rule_name,
                strategy=profile["strategy"],
                compliant=False,
                expected="NON_COMPLIANT",
                expected_versioning=profile["nc_versioning"],
                expected_lifecycle=profile["nc_lifecycle"],
            )

            _run_one_leg(
                config_mgr=config_mgr,
                compliance=compliance,
                s3_toggle=s3_toggle,
                s3_test_bucket=s3_test_bucket,
                rule_name=rule_name,
                strategy=profile["strategy"],
                compliant=True,
                expected="COMPLIANT",
                expected_versioning=profile["c_versioning"],
                expected_lifecycle=profile["c_lifecycle"],
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
