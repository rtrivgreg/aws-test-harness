"""CLOUDTRAIL_ALL_READ_S3_DATA_EVENT_CHECK — no S3 data events NC, all-read C."""

from __future__ import annotations

import os
import time

import boto3
import pytest

from harness.catalog import ManagedRuleSpec
from harness.cloudtrail_s3 import ensure_harness_trail
from harness.cloudtrail_toggle import CloudTrailToggle
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="cloudtrail-all-read-s3-data-event-check",
        source_identifier="CLOUDTRAIL_ALL_READ_S3_DATA_EVENT_CHECK",
        input_parameters={},
        resource_types=["AWS::::Account"],
        toggle_strategy="ct_s3_read_data",
    )


def _dump(config_mgr: ConfigRuleManager, compliance: ComplianceChecker, rule_name: str) -> None:
    config_mgr.dump_rule_debug(rule_name)
    rows = []
    for r in compliance.get_results_for_rule(rule_name):
        q = r.get("EvaluationResultIdentifier", {}).get("EvaluationResultQualifier", {})
        rows.append(f"{q.get('ResourceId')}:{r.get('ComplianceType')}:{r.get('Annotation')}")
    log(f"EvaluationResults ({len(rows)}): {rows}")


@pytest.mark.cloudtrail
@pytest.mark.s3
@pytest.mark.slow
def test_cloudtrail_all_read_s3_data_event_check(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    account = boto3.client("sts").get_caller_identity()["Account"]
    test_bucket = os.environ.get("S3_TEST_BUCKET", "")
    name, arn, created = ensure_harness_trail(aws_region, test_run_id, test_bucket)
    toggle = CloudTrailToggle(trail_name=name, trail_arn=arn, region=aws_region)
    spec = _spec()
    rule_name = None
    passed = False
    original = None
    try:
        original = toggle.get_event_selectors()
        log(f"===== Testing rule: {spec.rule_name} account={account} trail={name} =====")
        rule_name = config_mgr.put_managed_rule(
            spec, maximum_execution_frequency="TwentyFour_Hours"
        )

        toggle.set_s3_read_data_events(False)
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

        toggle.set_s3_read_data_events(True)
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
        log(f"{spec.rule_name} passed S3 read data-event cycle", style="green")
        passed = True
    finally:
        ct = boto3.client("cloudtrail", region_name=aws_region)
        if created:
            try:
                ct.delete_trail(Name=name)
                log(f"Deleted throwaway trail {name}")
            except Exception as exc:
                log(f"delete_trail: {exc}", style="yellow")
        elif original is not None:
            try:
                ct.put_event_selectors(
                    TrailName=name,
                    EventSelectors=original or [{
                        "ReadWriteType": "All",
                        "IncludeManagementEvents": True,
                        "DataResources": [],
                    }],
                )
                log("Restored original event selectors")
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
