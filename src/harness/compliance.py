"""
Compliance result helpers.
"""

from __future__ import annotations

import json
import time
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import is_dry_run, log


def _to_epoch(value) -> float:
    if value is None:
        return 0.0
    if hasattr(value, "timestamp"):
        return value.timestamp()
    return float(value)


class ComplianceChecker:
    def __init__(self, region: Optional[str] = None):
        self.region = region or "us-east-1"
        self.client = boto3.client("config", region_name=self.region)

    def wait_for_resource_discovered(
        self,
        resource_id: str,
        resource_type: str = "AWS::S3::Bucket",
        timeout_seconds: int = 300,
        poll_seconds: int = 5,
    ) -> None:
        if is_dry_run():
            log(f"Dry-run – skipping Config discovery wait for {resource_id}")
            return

        deadline = time.time() + timeout_seconds
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            try:
                resp = self.client.get_resource_config_history(
                    resourceType=resource_type,
                    resourceId=resource_id,
                    limit=1,
                )
                items = resp.get("configurationItems") or []
                if items:
                    status = items[0].get("configurationItemStatus", "?")
                    captured = items[0].get("configurationItemCaptureTime", "?")
                    log(
                        f"Config discovered {resource_id} "
                        f"(status={status}, captured={captured}, attempt={attempt})"
                    )
                    return
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code not in (
                    "ResourceNotDiscoveredException",
                    "NoAvailableConfigurationRecorderException",
                ):
                    raise RuntimeError(
                        f"get_resource_config_history failed for {resource_id}: {exc}"
                    ) from exc

            log(
                f"Waiting for Config to discover {resource_id} "
                f"(attempt {attempt}, up to {timeout_seconds}s)"
            )
            time.sleep(poll_seconds)

        raise TimeoutError(
            f"Timed out after {timeout_seconds}s waiting for Config to discover "
            f"{resource_type} {resource_id}. Check the configuration recorder."
        )

    def _latest_ci(self, resource_id: str, resource_type: str) -> Optional[dict]:
        try:
            resp = self.client.get_resource_config_history(
                resourceType=resource_type,
                resourceId=resource_id,
                limit=1,
            )
            items = resp.get("configurationItems") or []
            return items[0] if items else None
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in (
                "ResourceNotDiscoveredException",
                "NoAvailableConfigurationRecorderException",
            ):
                return None
            raise RuntimeError(
                f"get_resource_config_history failed for {resource_id}: {exc}"
            ) from exc

    @staticmethod
    def _s3_versioning_status(ci: dict) -> Optional[str]:
        supp = ci.get("supplementaryConfiguration") or {}
        raw = supp.get("BucketVersioningConfiguration") or supp.get(
            "VersioningConfiguration"
        )
        if not raw:
            return None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                return None
        if isinstance(raw, dict):
            return raw.get("status") or raw.get("Status")
        return None

    def wait_for_config_item_after(
        self,
        resource_id: str,
        after_timestamp: float,
        resource_type: str = "AWS::S3::Bucket",
        timeout_seconds: int = 300,
        poll_seconds: int = 5,
        expected_versioning: Optional[str] = None,
    ) -> None:
        if is_dry_run():
            log(f"Dry-run – skipping CI freshness wait for {resource_id}")
            return

        deadline = time.time() + timeout_seconds
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            ci = self._latest_ci(resource_id, resource_type)
            if ci:
                captured = ci.get("configurationItemCaptureTime")
                captured_epoch = _to_epoch(captured)
                ver = self._s3_versioning_status(ci)
                fresh = captured_epoch >= after_timestamp
                ver_ok = expected_versioning is None or (
                    ver is not None and ver.lower() == expected_versioning.lower()
                )

                if fresh and ver_ok:
                    log(
                        f"Config CI for {resource_id} is ready "
                        f"(captured={captured}, versioning={ver}, attempt={attempt})"
                    )
                    return

                log(
                    f"Config CI for {resource_id} not ready yet "
                    f"(captured={captured}, versioning={ver}, "
                    f"need_ts>={after_timestamp:.0f}, need_ver={expected_versioning}, "
                    f"attempt={attempt})"
                )
            else:
                log(f"No Config CI yet for {resource_id} (attempt={attempt})")

            time.sleep(poll_seconds)

        raise TimeoutError(
            f"Timed out after {timeout_seconds}s waiting for Config CI for "
            f"{resource_type} {resource_id} (need after {after_timestamp:.0f}, "
            f"versioning={expected_versioning})"
        )

    def get_results_for_rule(
        self,
        rule_name: str,
        compliance_types: Optional[List[str]] = None,
    ) -> List[dict]:
        if is_dry_run():
            log(f"Dry-run – returning empty compliance results for {rule_name}")
            return []

        kwargs: dict = {"ConfigRuleName": rule_name}
        if compliance_types:
            kwargs["ComplianceTypes"] = compliance_types

        results: List[dict] = []
        try:
            paginator = self.client.get_paginator("get_compliance_details_by_config_rule")
            for page in paginator.paginate(**kwargs):
                results.extend(page.get("EvaluationResults", []))
        except ClientError as exc:
            raise RuntimeError(f"GetComplianceDetailsByConfigRule failed: {exc}") from exc

        return results

    def _matching_results(
        self,
        results: List[dict],
        resource_id: str,
        after_timestamp: Optional[float] = None,
        expected: Optional[str] = None,
    ) -> List[dict]:
        matched = []
        for r in results:
            qual = (
                r.get("EvaluationResultIdentifier", {})
                .get("EvaluationResultQualifier", {})
            )
            if qual.get("ResourceId") != resource_id:
                continue
            if after_timestamp is not None:
                recorded = _to_epoch(
                    r.get("ResultRecordedTime") or r.get("ConfigRuleInvokedTime")
                )
                if recorded < after_timestamp:
                    continue
            if expected is not None and r.get("ComplianceType") != expected:
                continue
            matched.append(r)
        return matched

    def wait_for_resource_result(
        self,
        rule_name: str,
        resource_id: str,
        expected: str,
        timeout_seconds: int = 180,
        poll_seconds: int = 8,
        config_mgr=None,
        after_timestamp: Optional[float] = None,
    ) -> List[dict]:
        if is_dry_run():
            return []

        deadline = time.time() + timeout_seconds
        attempt = 0
        last_results: List[dict] = []

        while time.time() < deadline:
            attempt += 1
            last_results = self.get_results_for_rule(rule_name)
            matching = self._matching_results(
                last_results,
                resource_id,
                after_timestamp=after_timestamp,
                expected=expected,
            )
            if matching:
                matching.sort(
                    key=lambda r: _to_epoch(
                        r.get("ResultRecordedTime") or r.get("ConfigRuleInvokedTime")
                    ),
                    reverse=True,
                )
                log(
                    f"Found evaluation result for {resource_id} under {rule_name} "
                    f"(attempt {attempt}, compliance={matching[0].get('ComplianceType')})"
                )
                return matching

            # Show what we do see for this resource (even wrong type) for debugging
            any_for_resource = self._matching_results(
                last_results, resource_id, after_timestamp=after_timestamp
            )
            seen = [r.get("ComplianceType") for r in any_for_resource] or ["none"]
            log(
                f"Waiting for {expected} on {resource_id} under {rule_name} "
                f"(attempt {attempt}; post-ts types seen={seen})"
            )

            if config_mgr is not None and attempt % 3 == 0:
                try:
                    config_mgr.start_evaluation(rule_name)
                except Exception as exc:
                    log(f"Re-evaluation nudge failed (ignored): {exc}", style="yellow")

            time.sleep(poll_seconds)

        raise AssertionError(
            f"Timed out after {timeout_seconds}s waiting for {expected} on "
            f"resource {resource_id} under rule {rule_name} "
            f"(after_ts={after_timestamp}). Last results: {last_results}"
        )

    def assert_resource_compliance(
        self,
        rule_name: str,
        resource_id: str,
        expected: str,
        resource_type: str = "AWS::S3::Bucket",
        config_mgr=None,
        timeout_seconds: int = 180,
        after_timestamp: Optional[float] = None,
    ) -> None:
        if is_dry_run():
            log(f"Dry-run – would assert {resource_id} is {expected} under {rule_name}")
            return

        matching = self.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=resource_id,
            expected=expected,
            timeout_seconds=timeout_seconds,
            config_mgr=config_mgr,
            after_timestamp=after_timestamp,
        )

        actual = matching[0].get("ComplianceType")
        if actual != expected:
            raise AssertionError(
                f"Expected {resource_id} to be {expected} under {rule_name}, "
                f"but found {actual}"
            )

        log(f"✓ {resource_id} is {actual} under {rule_name}", style="green")
