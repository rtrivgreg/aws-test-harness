"""
Helpers for creating, evaluating and deleting AWS Config managed rules.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, ReadTimeoutError, ConnectTimeoutError
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
        self.client = boto3.client(
            "config",
            region_name=self.region,
            config=BotoConfig(
                connect_timeout=10, read_timeout=30, retries={"max_attempts": 3}
            ),
        )

    def _rule_name_for_run(self, base_name: str) -> str:
        import re

        safe = re.sub(r"[^a-zA-Z0-9_-]", "-", base_name)
        safe = re.sub(r"-+", "-", safe).strip("-")[:80]
        return f"harness-{safe}-{self.test_run_id}"

    @dry_run_guard("PutConfigRule")
    def put_managed_rule(
        self,
        spec: ManagedRuleSpec,
        resource_id: Optional[str] = None,
        maximum_execution_frequency: Optional[str] = None,
    ) -> str:
        rule_name = self._rule_name_for_run(spec.rule_name)
        log(f"Putting managed rule {rule_name} (source={spec.source_identifier})")

        config_rule: Dict[str, Any] = {
            "ConfigRuleName": rule_name,
            "Description": spec.description
            or f"Harness test for {spec.source_identifier}",
            "Source": {
                "Owner": "AWS",
                "SourceIdentifier": spec.source_identifier,
            },
            "InputParameters": json.dumps(spec.input_parameters)
            if spec.input_parameters
            else "{}",
        }

        if maximum_execution_frequency:
            config_rule["MaximumExecutionFrequency"] = maximum_execution_frequency

        if spec.resource_types:
            scope: Dict[str, Any] = {"ComplianceResourceTypes": spec.resource_types}
            if resource_id:
                scope["ComplianceResourceId"] = resource_id
                log(f"Scoping {rule_name} to {resource_id}")
            config_rule["Scope"] = scope

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

    def describe_evaluation_status(self, rule_name: str) -> dict:
        resp = self.client.describe_config_rule_evaluation_status(
            ConfigRuleNames=[rule_name]
        )
        statuses = resp.get("ConfigRulesEvaluationStatus", [])
        return statuses[0] if statuses else {}

    def describe_rule(self, rule_name: str) -> dict:
        resp = self.client.describe_config_rules(ConfigRuleNames=[rule_name])
        rules = resp.get("ConfigRules", [])
        return rules[0] if rules else {}

    def describe_compliance_by_rule(self, rule_name: str) -> dict:
        try:
            return self.client.describe_compliance_by_config_rule(
                ConfigRuleNames=[rule_name]
            )
        except ClientError as exc:
            return {"error": str(exc)}

    def dump_rule_debug(self, rule_name: str) -> None:
        status = self.describe_evaluation_status(rule_name)
        rule = self.describe_rule(rule_name)
        summary = self.describe_compliance_by_rule(rule_name)
        log(f"DEBUG rule={json.dumps(rule, default=str)[:2000]}")
        log(f"DEBUG status={json.dumps(status, default=str)[:2000]}")
        log(f"DEBUG compliance_summary={json.dumps(summary, default=str)[:2000]}")

    @dry_run_guard("DeleteConfigRule")
    def delete_rule(self, rule_name: str) -> None:
        log(f"Deleting Config rule {rule_name}")
        try:
            self.client.delete_config_rule(ConfigRuleName=rule_name)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchConfigRuleException", "ResourceNotFoundException"):
                log(f"Rule {rule_name} already gone")
            elif code == "ResourceInUseException":
                log(
                    f"Rule {rule_name} still in use; delete will complete asynchronously",
                    style="yellow",
                )
            else:
                log(f"Cleanup warning for {rule_name}: {exc}", style="yellow")
        except (ReadTimeoutError, ConnectTimeoutError, TimeoutError) as exc:
            log(f"Cleanup timeout for {rule_name} (ignored): {exc}", style="yellow")
        except Exception as exc:
            log(f"Cleanup warning for {rule_name}: {exc}", style="yellow")

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

    @retry(
        stop=stop_after_attempt(40),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    def wait_for_evaluation(self, rule_name: str, after_timestamp: float) -> None:
        if is_dry_run():
            log(f"Dry-run – skipping wait for evaluation of {rule_name}")
            return

        status = self.describe_evaluation_status(rule_name)
        if not status:
            raise RuntimeError(f"No evaluation status returned for {rule_name}")

        last_eval = status.get("LastSuccessfulEvaluationTime")
        last_inv = status.get("LastSuccessfulInvocationTime")
        last_success = last_eval or last_inv
        last_failed = status.get("LastFailedEvaluationTime") or status.get(
            "LastFailedInvocationTime"
        )
        last_error = status.get("LastErrorCode")
        last_msg = status.get("LastErrorMessage")
        first_started = status.get("FirstEvaluationStarted")

        if last_success is None:
            log(
                f"Waiting for evaluation of {rule_name} "
                f"(first_started={first_started}, last_failed={last_failed}, "
                f"error={last_error}: {last_msg})"
            )
            raise RuntimeError(
                f"Evaluation has not completed yet for {rule_name} "
                f"(first_started={first_started}, last_error={last_error}, "
                f"last_msg={last_msg})"
            )

        last_epoch = (
            last_success.timestamp()
            if hasattr(last_success, "timestamp")
            else float(last_success)
        )
        if last_epoch < after_timestamp:
            log(
                f"Waiting for evaluation of {rule_name} newer than {after_timestamp:.0f} "
                f"(last_success={last_success})"
            )
            raise RuntimeError(
                "Evaluation timestamp is still older than the change we made"
            )

        log(
            f"Evaluation completed for {rule_name} at {last_success} "
            f"(eval={last_eval}, inv={last_inv})"
        )
