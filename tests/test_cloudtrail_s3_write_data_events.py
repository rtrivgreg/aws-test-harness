"""CLOUDTRAIL_ALL_WRITE_S3_DATA_EVENT_CHECK — no S3 data events NC, all-write C.

Periodic AWS::::Account rule. Uses existing harness trail if present.
"""

from __future__ import annotations

import os
import time

import boto3
import pytest

from harness.catalog import ManagedRuleSpec
from harness.cloudtrail_toggle import CloudTrailToggle
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="cloudtrail-all-write-s3-data-event-check",
        source_identifier="CLOUDTRAIL_ALL_WRITE_S3_DATA_EVENT_CHECK",
        input_parameters={},
        resource_types=["AWS::::Account"],
        toggle_strategy="ct_s3_write_data",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> None:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}")
    log(f"EvaluationResults ({len(rows)}): {rows}")


def _find_trail(region: str, test_run_id: str) -> dict:
    ct = boto3.client("cloudtrail", region_name=region)
    trails = ct.describe_trails().get("trailList") or []
    preferred = [t for t in trails if test_run_id in (t.get("Name") or "")]
    pool = preferred or trails
    if not pool:
        raise RuntimeError("No CloudTrail trail in this account/region")
    trail = pool[0]
    log(f"Using trail {trail.get('Name')} multi={trail.get('IsMultiRegionTrail')}")
    return trail


@pytest.mark.cloudtrail
@pytest.mark.s3
@pytest.mark.slow
def test_cloudtrail_all_write_s3_data_event_check(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    account = boto3.client("sts").get_caller_identity()["Account"]
    trail = _find_trail(aws_region, test_run_id)
    if not trail.get("IsMultiRegionTrail"):
        pytest.skip("Need a multi-Region trail for this identifier")
    toggle = CloudTrailToggle(
        trail_name=trail["Name"],
        trail_arn=trail.get("TrailARN"),
        region=aws_region,
    )
    spec = _spec()
    rule_name = None
    passed = False
    original = toggle.get_event_selectors()
    try:
        log(f"===== Testing rule: {spec.rule_name} account={account} =====")
        rule_name = config_mgr.put_managed_rule(
            spec, maximum_execution_frequency="TwentyFour_Hours"
        )

        toggle.set_s3_write_data_events(False)
        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=account,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        toggle.set_s3_write_data_events(True)
        eval_ts = time.time() - 30
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        _dump(config_mgr, compliance, rule_name)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=account,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=300,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed S3 write data-event cycle", style="green")
        passed = True
    finally:
        try:
            if original:
                boto3.client("cloudtrail", region_name=aws_region).put_event_selectors(
                    TrailName=trail["Name"], EventSelectors=original
                )
                log("Restored original event selectors")
            else:
                toggle.set_s3_write_data_events(False)
        except Exception as exc:
            log(f"restore selectors: {exc}", style="yellow")
        keep = os.environ.get("HARNESS_KEEP_ON_FAIL") == "1" and not passed
        if keep:
            log(f"KEEP on fail: rule={rule_name}", style="yellow")
        elif rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
