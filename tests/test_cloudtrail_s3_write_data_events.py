"""CLOUDTRAIL_ALL_WRITE_S3_DATA_EVENT_CHECK — no S3 data events NC, all-write C.

Periodic AWS::::Account. Only use cfg-ct-* / harness trails. Never touch
kinesis-video-events or other account trails. Create a throwaway multi-Region
trail on the live logs bucket if no harness trail exists.
"""

from __future__ import annotations

import json
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


def _harness_trails(ct, test_run_id: str) -> list[dict]:
    trails = ct.describe_trails().get("trailList") or []
    out = []
    for t in trails:
        name = t.get("Name") or ""
        if name.startswith("cfg-ct-") or test_run_id in name:
            out.append(t)
    return out


def _ensure_trail(region: str, test_run_id: str, logs_bucket: str) -> tuple[dict, bool]:
    ct = boto3.client("cloudtrail", region_name=region)
    existing = _harness_trails(ct, test_run_id)
    if existing:
        trail = existing[0]
        log(f"Using harness trail {trail.get('Name')} multi={trail.get('IsMultiRegionTrail')}")
        return trail, False
    if not logs_bucket:
        raise RuntimeError("No harness trail and S3_TEST_BUCKET unset")
    account = boto3.client("sts").get_caller_identity()["Account"]
    name = f"cfg-ct-s3w-{test_run_id}"
    s3 = boto3.client("s3", region_name=region)
    prefix_bucket = logs_bucket if "logs" in logs_bucket else f"cfg-test-logs-{test_run_id}-ca589695"
    # Prefer explicit logs bucket if the live test bucket was passed.
    bucket = os.environ.get("S3_LOGS_BUCKET") or (
        logs_bucket.replace("cfg-test-", "cfg-test-logs-", 1)
        if logs_bucket.startswith("cfg-test-") and "logs" not in logs_bucket.split("cfg-test-")[-1][:6]
        else logs_bucket
    )
    log(f"Creating throwaway trail {name} -> s3://{bucket}")
    created = ct.create_trail(
        Name=name,
        S3BucketName=bucket,
        IsMultiRegionTrail=True,
        EnableLogFileValidation=True,
    )
    ct.start_logging(Name=name)
    created["Name"] = name
    created["IsMultiRegionTrail"] = True
    return created, True


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
    logs_bucket = os.environ.get("S3_TEST_BUCKET", "")
    trail, created = _ensure_trail(aws_region, test_run_id, logs_bucket)
    name = trail["Name"]
    if not trail.get("IsMultiRegionTrail"):
        if created:
            boto3.client("cloudtrail", region_name=aws_region).delete_trail(Name=name)
        pytest.skip("Need a multi-Region trail for this identifier")
    toggle = CloudTrailToggle(
        trail_name=name,
        trail_arn=trail.get("TrailARN"),
        region=aws_region,
    )
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
        ct = boto3.client("cloudtrail", region_name=aws_region)
        if created:
            try:
                ct.delete_trail(Name=name)
                log(f"Deleted throwaway trail {name}")
            except Exception as exc:
                log(f"delete_trail: {exc}", style="yellow")
        elif original is not None:
            try:
                ct.put_event_selectors(TrailName=name, EventSelectors=original or [{
                    "ReadWriteType": "All",
                    "IncludeManagementEvents": True,
                    "DataResources": [],
                }])
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
