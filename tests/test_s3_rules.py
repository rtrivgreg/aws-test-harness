"""
First vertical slice – S3 managed rules.

For every S3 rule returned by the live DynamoDB catalog we:

1. Put the managed rule with the exact parameters from the catalog.
2. Force the shared test bucket into a NON_COMPLIANT state.
3. Start evaluation, wait, assert NON_COMPLIANT.
4. Force the bucket into a COMPLIANT state.
5. Re-evaluate, assert COMPLIANT.
6. Clean up the Config rule.

The concrete toggle used for each rule is taken from the catalog's
``toggle_strategy`` field (defaults to ``s3_generic`` → versioning).
"""

from __future__ import annotations

import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.s3_toggle import S3Toggle


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
    Parametrized-style loop over every S3 rule from the catalog.
    Using a single test function keeps fixture setup cheap; each rule
    still gets its own independent Put → evaluate → Delete cycle.
    """
    if not s3_rules:
        pytest.skip("No S3 rules available from the catalog")

    failures: list[str] = []

    for spec in s3_rules:
        rule_name = None
        try:
            log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")

            # a. PutConfigRule
            rule_name = config_mgr.put_managed_rule(spec)

            # b. (light) assert it exists – DescribeConfigRules would be ideal;
            #    for brevity we rely on the fact that Put succeeded.

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
            # i. Always clean up the rule
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
