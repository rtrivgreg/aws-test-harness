"""
Compliance result helpers.

Important: DescribeConfigRuleEvaluationStatus only tells you that an
evaluation *ran*.  The actual COMPLIANT / NON_COMPLIANT / NOT_APPLICABLE
outcome lives in GetComplianceDetailsByConfigRule (or ByResource).
"""

from __future__ import annotations

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
        """
        Return the list of EvaluationResult objects for the given rule.
        """
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

    def assert_resource_compliance(
        self,
        rule_name: str,
        resource_id: str,
        expected: str,
        resource_type: str = "AWS::S3::Bucket",
    ) -> None:
        """
        Assert that the given resource has the expected compliance type
        under the given rule.

        expected should be one of: COMPLIANT, NON_COMPLIANT, NOT_APPLICABLE
        """
        if is_dry_run():
            log(f"Dry-run – would assert {resource_id} is {expected} under {rule_name}")
            return

        results = self.get_results_for_rule(rule_name)
        matching = [
            r
            for r in results
            if r.get("EvaluationResultIdentifier", {})
            .get("EvaluationResultQualifier", {})
            .get("ResourceId")
            == resource_id
        ]

        if not matching:
            # Fallback: sometimes the resource has not been evaluated yet
            raise AssertionError(
                f"No evaluation result found for resource {resource_id} "
                f"under rule {rule_name}. Full results: {results}"
            )

        actual = matching[0].get("ComplianceType")
        if actual != expected:
            raise AssertionError(
                f"Expected {resource_id} to be {expected} under {rule_name}, "
                f"but found {actual}"
            )

        log(f"✓ {resource_id} is {actual} under {rule_name}", style="green")
