"""
EBS_SNAPSHOT_PUBLIC_RESTORABLE_CHECK is periodic and account-scoped:
NON_COMPLIANT if ANY snapshot is publicly restorable.
"""

from __future__ import annotations

import time

import pytest

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.ebs_toggle import EbsToggle


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="ebs-snapshot-public-restorable-check",
        source_identifier="EBS_SNAPSHOT_PUBLIC_RESTORABLE_CHECK",
        input_parameters={},
        resource_types=[],
        description="Periodic account-level snapshot public check",
        toggle_strategy="ebs_snapshot_public",
    )


def _annotation(results: list[dict]) -> str:
    for r in results:
        if r.get("Annotation"):
            return str(r["Annotation"])
    return ""


def _any_result_of_type(results: list[dict], expected: str) -> bool:
    return any(r.get("ComplianceType") == expected for r in results)


@pytest.mark.ebs
@pytest.mark.slow
def test_ebs_snapshot_public_restorable(
    ebs_volumes: dict,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    snap = ebs_volumes.get("unencrypted_snapshot_id")
    if not snap:
        pytest.fail("ebs_unencrypted_snapshot_id missing from terraform outputs")

    toggle = EbsToggle(snapshot_id=snap, region=aws_region)
    spec = _spec()
    rule_name = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        rule_name = config_mgr.put_managed_rule(spec)

        toggle.make_snapshot_public()
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        results = compliance.get_results_for_rule(rule_name)
        if not _any_result_of_type(results, "NON_COMPLIANT"):
            raise AssertionError(
                f"Expected NON_COMPLIANT after public snapshot; "
                f"annotation={_annotation(results)} results={results}"
            )
        log(
            f"public snapshot produced NON_COMPLIANT ({_annotation(results)})",
            style="green",
        )

        toggle.make_snapshot_private()
        # Periodic rules can still see the old public count for a short window.
        time.sleep(15)
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        results = compliance.get_results_for_rule(rule_name)
        if _any_result_of_type(results, "NON_COMPLIANT"):
            raise AssertionError(
                "Still NON_COMPLIANT after making harness snapshot private. "
                f"EC2 says public={toggle.is_public()}. "
                f"annotation={_annotation(results)}. "
                "If annotation count stays at 1, another snapshot in the account "
                "is public, or Config has not refreshed snapshot permissions yet."
            )
        log("private snapshot produced no NON_COMPLIANT", style="green")
    finally:
        try:
            toggle.make_snapshot_private()
        except Exception:
            pass
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
