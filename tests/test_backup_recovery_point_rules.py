"""BACKUP_RECOVERY_POINT_ENCRYPTED — unencrypted EBS RP vs encrypted EBS RP.

EBS recovery-point ARNs are EC2 snapshot ARNs, not
arn:aws:backup:...:recovery-point:. Config may not inventory them as
AWS::Backup::RecoveryPoint (same class of miss as FSx).
"""

from __future__ import annotations

import time

import boto3
import pytest
from botocore.exceptions import ClientError

from harness.backup_toggle import RecoveryPointHarness
from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="backup-recovery-point-encrypted",
        source_identifier="BACKUP_RECOVERY_POINT_ENCRYPTED",
        input_parameters={},
        resource_types=["AWS::Backup::RecoveryPoint"],
        toggle_strategy="backup_recovery_point_encrypted",
    )


def _candidate_ids(rp_arn: str) -> list[str]:
    ids = [rp_arn]
    if ":snapshot/" in rp_arn:
        snap = rp_arn.rsplit("/", 1)[-1]
        ids.append(snap)
    return ids


def _list_discovered(region: str) -> list[dict]:
    client = boto3.client("config", region_name=region)
    ids: list[dict] = []
    token = None
    while True:
        kwargs = {"resourceType": "AWS::Backup::RecoveryPoint"}
        if token:
            kwargs["nextToken"] = token
        resp = client.list_discovered_resources(**kwargs)
        ids.extend(resp.get("resourceIdentifiers") or [])
        token = resp.get("nextToken")
        if not token:
            break
    return ids


def _resolve_config_id(rp_arn: str, region: str, timeout: int = 180) -> str:
    candidates = _candidate_ids(rp_arn)
    deadline = time.time() + timeout
    last: list[dict] = []
    while time.time() < deadline:
        last = _list_discovered(region)
        found_ids = [i.get("resourceId") for i in last]
        log(f"Config AWS::Backup::RecoveryPoint ids={found_ids[:20]} (n={len(found_ids)})")
        for cand in candidates:
            if cand in found_ids:
                log(f"Matched Config resourceId {cand} for {rp_arn}")
                return cand
            for rid in found_ids:
                if rid and (rid.endswith(cand) or cand.endswith(rid)):
                    log(f"Fuzzy-matched Config resourceId {rid} for {rp_arn}")
                    return rid
        time.sleep(15)
    sample = [
        f"{i.get('resourceId')}|{i.get('resourceName')}" for i in last[:12]
    ]
    pytest.fail(
        "PARK candidate: Config did not discover AWS::Backup::RecoveryPoint "
        f"for {rp_arn} after {timeout}s. candidates={candidates}. "
        f"discovered_sample={sample}. Same class as FSx OpenZFS miss. "
        "Do not rerun until list-discovered-resources returns this RP."
    )


@pytest.mark.backup
@pytest.mark.slow
def test_backup_recovery_point_encrypted(
    test_run_id: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    harness = RecoveryPointHarness(test_run_id=test_run_id, region=aws_region)
    spec = _spec()
    rule_name = None
    provisioned = False
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        resources = harness.provision()
        provisioned = True
        nc_arn = resources["nc_rp_arn"]
        c_arn = resources["c_rp_arn"]
        log(f"NC RP ARN={nc_arn} C RP ARN={c_arn}")

        nc_id = _resolve_config_id(nc_arn, aws_region)
        rule_name = config_mgr.put_managed_rule(spec, resource_id=nc_id)
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        nc_hits = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=nc_id,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=600,
        )
        assert nc_hits[0]["ComplianceType"] == "NON_COMPLIANT"
        log(f"{nc_id} is NON_COMPLIANT under {rule_name}", style="green")

        c_id = _resolve_config_id(c_arn, aws_region)
        rule_name = config_mgr.put_managed_rule(spec, resource_id=c_id)
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        c_hits = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=c_id,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=600,
        )
        assert c_hits[0]["ComplianceType"] == "COMPLIANT"
        log(f"{c_id} is COMPLIANT under {rule_name}", style="green")
        log(f"{spec.rule_name} passed encrypted-RP cycle", style="green")
    finally:
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
        try:
            harness.cleanup()
        except ClientError as exc:
            log(f"cleanup: {exc}", style="yellow")
