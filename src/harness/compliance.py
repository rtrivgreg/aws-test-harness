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


def _parse_supp(raw):
    if raw is None:
        return None
    if isinstance(raw, str):
        if raw in ("", "null", "None"):
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw


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
        raw = _parse_supp(
            supp.get("BucketVersioningConfiguration")
            or supp.get("VersioningConfiguration")
        )
        if isinstance(raw, dict):
            return raw.get("status") or raw.get("Status")
        return None

    @staticmethod
    def _s3_has_lifecycle(ci: dict) -> Optional[bool]:
        supp = ci.get("supplementaryConfiguration") or {}
        raw = _parse_supp(
            supp.get("BucketLifecycleConfiguration")
            or supp.get("LifecycleConfiguration")
            or supp.get("BucketLifecycleConfigurationList")
        )
        if raw is None:
            return False
        if isinstance(raw, dict):
            rules = raw.get("rules") or raw.get("Rules") or []
            return bool(rules)
        if isinstance(raw, list):
            return bool(raw)
        return None

    @staticmethod
    def _s3_has_encryption(ci: dict) -> Optional[bool]:
        supp = ci.get("supplementaryConfiguration") or {}
        raw = _parse_supp(
            supp.get("ServerSideEncryptionConfiguration")
            or supp.get("BucketEncryption")
            or supp.get("BucketServerSideEncryptionConfiguration")
        )
        if raw is None:
            return False
        if isinstance(raw, dict):
            rules = raw.get("rules") or raw.get("Rules") or []
            return bool(rules)
        if isinstance(raw, list):
            return bool(raw)
        return None

    @staticmethod
    def _s3_public_access_fully_blocked(ci: dict) -> Optional[bool]:
        supp = ci.get("supplementaryConfiguration") or {}
        raw = _parse_supp(
            supp.get("PublicAccessBlockConfiguration")
            or supp.get("BucketPublicAccessBlockConfiguration")
        )
        if not isinstance(raw, dict):
            return None

        def flag(keys):
            for k in keys:
                if k in raw:
                    return bool(raw[k])
            return None

        vals = [
            flag(("blockPublicAcls", "BlockPublicAcls")),
            flag(("ignorePublicAcls", "IgnorePublicAcls")),
            flag(("blockPublicPolicy", "BlockPublicPolicy")),
            flag(("restrictPublicBuckets", "RestrictPublicBuckets")),
        ]
        if any(v is None for v in vals):
            return None
        return all(vals)

    def wait_for_config_item_after(
        self,
        resource_id: str,
        after_timestamp: float,
        resource_type: str = "AWS::S3::Bucket",
        timeout_seconds: int = 300,
        poll_seconds: int = 5,
        expected_versioning: Optional[str] = None,
        expected_lifecycle: Optional[bool] = None,
        expected_encryption: Optional[bool] = None,
        expected_public_blocked: Optional[bool] = None,
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
                has_lc = self._s3_has_lifecycle(ci)
                has_enc = self._s3_has_encryption(ci)
                pub_blocked = self._s3_public_access_fully_blocked(ci)

                fresh = captured_epoch >= after_timestamp
                ver_ok = expected_versioning is None or (
                    ver is not None and ver.lower() == expected_versioning.lower()
                )
                lc_ok = expected_lifecycle is None or has_lc is expected_lifecycle
                enc_ok = expected_encryption is None or has_enc is expected_encryption
                pub_ok = (
                    expected_public_blocked is None
                    or pub_blocked is expected_public_blocked
                )

                if fresh and ver_ok and lc_ok and enc_ok and pub_ok:
                    log(
                        f"Config CI for {resource_id} is ready "
                        f"(captured={captured}, ver={ver}, lc={has_lc}, "
                        f"enc={has_enc}, pubBlocked={pub_blocked}, attempt={attempt})"
                    )
                    return

                log(
                    f"Config CI for {resource_id} not ready yet "
                    f"(captured={captured}, ver={ver}, lc={has_lc}, enc={has_enc}, "
                    f"pubBlocked={pub_blocked}, need_ts>={after_timestamp:.0f}, "
                    f"need_ver={expected_versioning}, need_lc={expected_lifecycle}, "
                    f"need_enc={expected_encryption}, need_pub={expected_public_blocked}, "
                    f"attempt={attempt})"
                )
            else:
                log(f"No Config CI yet for {resource_id} (attempt={attempt})")

            time.sleep(poll_seconds)

        raise TimeoutError(
            f"Timed out after {timeout_seconds}s waiting for Config CI for "
            f"{resource_type} {resource_id}"
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
