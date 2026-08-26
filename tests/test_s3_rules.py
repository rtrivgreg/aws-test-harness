"""
S3 managed-rule compliance cycles.

Default allowlist: versioning, lifecycle, public-access.
S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED is intentionally omitted: modern S3
default encryption means delete_bucket_encryption does not produce a CI with
encryption absent, so the NON_COMPLIANT leg cannot be proven this way.
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
    "S3_BUCKET_VERSIONING_ENABLED",
    "s3-bucket-versioning-enabled",
    "RULE#s3-bucket-versioning-enabled",
    "S3_LIFECYCLE_POLICY_CHECK",
    "s3-lifecycle-policy-check",
    "RULE#s3-lifecycle-policy-check",
    "S3_VERSION_LIFECYCLE_POLICY_CHECK",
    "s3-version-lifecycle-policy-check",
    "RULE#s3-version-lifecycle-policy-check",
    "S3_BUCKET_LEVEL_PUBLIC_ACCESS_PROHIBITED",
    "s3-bucket-level-public-access-prohibited",
    "RULE#s3-bucket-level-public-access-prohibited",
}

RULE_PROFILES = {
    "S3_BUCKET_VERSIONING_ENABLED": {
        "strategy": "s3_versioning",
        "nc": {"versioning": "Suspended"},
        "c": {"versioning": "Enabled"},
    },
    "S3_LIFECYCLE_POLICY_CHECK": {
        "strategy": "s3_lifecycle",
        "nc": {"lifecycle": False},
        "c": {"lifecycle": True},
    },
    "S3_VERSION_LIFECYCLE_POLICY_CHECK": {
        "strategy": "s3_version_lifecycle",
        "nc": {"versioning": "Enabled", "lifecycle": False},
        "c": {"versioning": "Enabled", "lifecycle": True},
    },
    # Kept for optional manual runs; not in DEFAULT_ALLOWLIST
    "S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED": {
        "strategy": "s3_encryption",
        "nc": {"encryption": False},
        "c": {"encryption": True},
    },
    "S3_BUCKET_LEVEL_PUBLIC_ACCESS_PROHIBITED": {
        "strategy": "s3_public_access",
        "nc": {"public_blocked": False},
        "c": {"public_blocked": True},
    },
}


def _is_allowed(spec: ManagedRuleSpec) -> bool:
    if os.environ.get("ALLOW_ALL_S3_RULES") == "1":
        return True
    tokens = (
        "s3-bucket-versioning-enabled",
        "s3-lifecycle-policy-check",
        "s3-version-lifecycle-policy-check",
        "s3-bucket-level-public-access-prohibited",
    )
    return (
        spec.source_identifier in DEFAULT_ALLOWLIST
        or spec.rule_name in DEFAULT_ALLOWLIST
        or any(t in spec.rule_name for t in tokens)
    )


def _profile_for(spec: ManagedRuleSpec) -> dict:
    if spec.source_identifier in RULE_PROFILES:
        return RULE_PROFILES[spec.source_identifier]
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
    expectations: dict,
) -> None:
    s3_toggle.apply_strategy(strategy, compliant=compliant)
    change_ts = time.time()
    compliance.wait_for_config_item_after(
        resource_id=s3_test_bucket,
        after_timestamp=change_ts,
        resource_type="AWS::S3::Bucket",
        expected_versioning=expectations.get("versioning"),
        expected_lifecycle=expectations.get("lifecycle"),
        expected_encryption=expectations.get("encryption"),
        expected_public_blocked=expectations.get("public_blocked"),
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
                expectations=profile["nc"],
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
                expectations=profile["c"],
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
