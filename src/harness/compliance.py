"""
Compliance result helpers.

Important: DescribeConfigRuleEvaluationStatus only tells you that an
evaluation *ran*.  The actual COMPLIANT / NON_COMPLIANT / NOT_APPLICABLE
outcome lives in GetComplianceDetailsByConfigRule (or ByResource).

Newly created resources and post-change state both lag in Config. We:
1. Wait for Config to discover the resource before any rule work.
2. After each resource mutation, wait for a newer configuration item.
3. Poll evaluation results until the target resource ID appears.
"""

from __future__ import annotations

import time
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import is_dry_run, log


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
        """Block until Config has at least one configuration item for the resource."""
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

    def wait_for_config_item_after(
        self,
        resource_id: str,
        after_timestamp: float,
        resource_type: str = "AWS::S3::Bucket",
        timeout_seconds: int = 180,
        poll_seconds: int = 5,
    ) -> None:
        """
        Wait until Config has a configuration item with capture time >= after_timestamp.

        Call this after mutating the resource (e.g. toggling versioning) so the
        next evaluation uses the new state instead of a stale CI.
        """
        if is_dry_run():
            log(f"Dry-run – skipping CI freshness wait for {resource_id}")
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
                    captured = items[0].get("configurationItemCaptureTime")
                    if captured is not None:
                        captured_epoch = (
                            captured.timestamp()
                            if hasattr(captured, "timestamp")
                            else float(captured)
                        )
                        if captured_epoch >= after_timestamp:
                            log(
                                f"Config CI for {resource_id} is fresh "
                                f"(captured={captured}, attempt={attempt})"
                            )
                            return
                        log(
                            f"Config CI for {resource_id} still stale "
                            f"(captured={captured}, need >= {after_timestamp:.0f}, "
                            f"attempt={attempt})"
                        )
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code not in (
                    "ResourceNotDiscoveredException",
                    "NoAvailableConfigurationRecorderException",
                ):
                    raise RuntimeError(
                        f"get_resource_config_history failed for {resource_id}: {exc}"
                    ) from exc

            time.sleep(poll_seconds)

        raise TimeoutError(
            f"Timed out after {timeout_seconds}s waiting for a fresh Config CI "
            f"for {resource_type} {resource_id} after {after_timestamp:.0f}"
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

    def _matching_results(self, results: List[dict], resource_id: str) -> List[dict]:
        return [
            r
            for r in results
            if r.get("EvaluationResultIdentifier", {})
            .get("EvaluationResultQualifier", {})
            .get("ResourceId")
            == resource_id
        ]

    def wait_for_resource_result(
        self,
        rule_name: str,
        resource_id: str,
        timeout_seconds: int = 180,
        poll_seconds: int = 10,
        config_mgr=None,
    ) -> List[dict]:
        if is_dry_run():
            return []

        deadline = time.time() + timeout_seconds
        attempt = 0
        last_results: List[dict] = []

        while time.time() < deadline:
            attempt += 1
            last_results = self.get_results_for_rule(rule_name)
            matching = self._matching_results(last_results, resource_id)
            if matching:
                log(
                    f"Found evaluation result for {resource_id} under {rule_name} "
                    f"(attempt {attempt})"
                )
                return matching

            log(
                f"Waiting for Config to evaluate {resource_id} under {rule_name} "
                f"(attempt {attempt}; {len(last_results)} other result(s) so far)"
            )

            if config_mgr is not None and attempt % 3 == 0:
                try:
                    config_mgr.start_evaluation(rule_name)
                except Exception as exc:
                    log(f"Re-evaluation nudge failed (ignored): {exc}", style="yellow")

            time.sleep(poll_seconds)

        raise AssertionError(
            f"Timed out after {timeout_seconds}s waiting for resource {resource_id} "
            f"under rule {rule_name}. Last results: {last_results}"
        )

    def assert_resource_compliance(
        self,
        rule_name: str,
        resource_id: str,
        expected: str,
        resource_type: str = "AWS::S3::Bucket",
        config_mgr=None,
        timeout_seconds: int = 180,
    ) -> None:
        if is_dry_run():
            log(f"Dry-run – would assert {resource_id} is {expected} under {rule_name}")
            return

        matching = self.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=resource_id,
            timeout_seconds=timeout_seconds,
            config_mgr=config_mgr,
        )

        actual = matching[0].get("ComplianceType")
        if actual != expected:
            raise AssertionError(
                f"Expected {resource_id} to be {expected} under {rule_name}, "
                f"but found {actual}"
            )

        log(f"✓ {resource_id} is {actual} under {rule_name}", style="green")
