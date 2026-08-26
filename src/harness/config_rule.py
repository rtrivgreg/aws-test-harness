"""
Helpers for creating, evaluating and deleting AWS Config managed rules.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from harness.catalog import ManagedRuleSpec
from harness.dry_run import dry_run_guard, is_dry_run, log
from harness.tags import standard_tags


class RateLimitedError(Exception):
    """Raised so tenacity can retry StartConfigRulesEvaluation."""


class ConfigRuleManager:
    def __init__(self, region: Optional[str] = None, test_run_id: str = "unknown"):
        self.region = region or "us-east-1"
        self.test_run_id = test_run_id
        self.client = boto3.client("config", region_name=self.region)

    def _rule_name_for_run(self, base_name: str) -> str:
        """Make the Config rule name unique per test run and valid for AWS Config."""
        import re

        safe = re.sub(r"[^a-zA-Z0-9_-]", "-", base_name)
        safe = re.sub(r"-+", "-", safe).strip("-")[:80]
        return f"harness-{safe}-{self.test_run_id}"

    @dry_run_guard("PutConfigRule")
    def put_managed_rule(self, spec: ManagedRuleSpec) -> str:
        """Create (or update) a managed Config rule; return the concrete rule name."""
        rule_name = self._rule_name_for_run(spec.rule_name)
        log(f"Putting managed rule {rule_name} (source={spec.source_identifier})")

        config_rule: Dict[str, Any] = {
            "ConfigRuleName": rule_name,
            "Description": spec.description or f"Harness test for {spec.source_identifier}",
            "Source": {
                "Owner": "AWS",
                "SourceIdentifier": spec.source_identifier,
            },
            "InputParameters": json.dumps(spec.input_parameters)
            if spec.input_parameters
            else "{}",
        }

        if spec.resource_types:
            config_rule["Scope"] = {"ComplianceResourceTypes": spec.resource_types}

        try:
            self.client.put_config_rule(ConfigRule=config_rule)
        except ClientError as exc:
            raise RuntimeError(f"PutConfigRule failed for {rule_name}: {exc}") from exc

        try:
            self.client.tag_resource(
                ResourceArn=self._rule_arn(rule_name),
                Tags=[
                    {"Key": k, "Value": v}
                    for k, v in standard_tags(self.test_run_id).items()
                ],
            )
        except ClientError:
            log(f"Warning: could not tag rule {rule_name}", style="yellow")

        return rule_name

    def _rule_arn(self, rule_name: str) -> str:
        account = boto3.client("sts").get_caller_identity()["Account"]
        return f"arn:aws:config:{self.region}:{account}:config-rule/{rule_name}"

    @dry_run_guard("DeleteConfigRule")
    def delete_rule(self, rule_name: str) -> None:
        log(f"Deleting Config rule {rule_name}")
        try:
            self.client.delete_config_rule(ConfigRuleName=rule_name)
        except ClientError as exc:
            if "NoSuchConfigRuleException" in str(exc):
                log(f"Rule {rule_name} already gone")
            else:
                raise

    @retry(
        retry=retry_if_exception_type(RateLimitedError),
        stop=stop_after_attempt(8),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        reraise=True,
    )
    def start_evaluation(self, rule_name: str) -> None:
        if is_dry_run():
            log(f"Would StartConfigRulesEvaluation for {rule_name}")
            return
        log(f"Starting on-demand evaluation for {rule_name}")
        try:
            self.client.start_config_rules_evaluation(ConfigRuleNames=[rule_name])
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code == "LimitExceededException":
                log(
                    f"Rate limited on StartConfigRulesEvaluation for {rule_name}; backing off…",
                    style="yellow",
                )
                raise RateLimitedError(str(exc)) from exc
            raise

    @retry(stop=stop_after_attempt(30), wait=wait_exponential(multiplier=1, min=2, max=15))
    def wait_for_evaluation(self, rule_name: str, after_timestamp: float) -> None:
        """Poll until a successful evaluation newer than *after_timestamp*."""
        if is_dry_run():
            log(f"Dry-run – skipping wait for evaluation of {rule_name}")
            return

        resp = self.client.describe_config_rule_evaluation_status(
            ConfigRuleNames=[rule_name]
        )
        statuses = resp.get("ConfigRulesEvaluationStatus", [])
        if not statuses:
            raise RuntimeError(f"No evaluation status returned for {rule_name}")

        status = statuses[0]
        last_success = status.get("LastSuccessfulEvaluationTime")
        if last_success is None:
            raise RuntimeError("Evaluation has not completed yet")

        last_epoch = (
            last_success.timestamp()
            if hasattr(last_success, "timestamp")
            else float(last_success)
        )
        if last_epoch < after_timestamp:
            raise RuntimeError(
                "Evaluation timestamp is still older than the change we made"
            )

        log(f"Evaluation completed for {rule_name} at {last_success}")
