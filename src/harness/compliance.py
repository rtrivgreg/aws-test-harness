"""
Compliance result helpers.

Important: DescribeConfigRuleEvaluationStatus only tells you that an
evaluation *ran*.  The actual COMPLIANT / NON_COMPLIANT / NOT_APPLICABLE
outcome lives in GetComplianceDetailsByConfigRule (or ByResource).

Newly created resources are often missing from the first evaluation wave.
assert_resource_compliance therefore polls until the target resource ID
appears (or times out).
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

    def get_results_for_rule(
        self,
        rule_name: str,
        compliance_types: Optional[List[str]] = None,
    ) -> List[dict]:
        """Return the list of EvaluationResult objects for the given rule."""
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
        """
        Poll until evaluation results include *resource_id*.

        Optionally re-triggers StartConfigRulesEvaluation via config_mgr
        every other poll to give Config another chance to pick up a new resource.
        """
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

            # Periodically nudge another evaluation in case the first wave missed the new bucket
            if config_mgr is not None and attempt % 2 == 0:
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
        """
        Assert that the given resource has the expected compliance type
        under the given rule.

        expected should be one of: COMPLIANT, NON_COMPLIANT, NOT_APPLICABLE
        """
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
