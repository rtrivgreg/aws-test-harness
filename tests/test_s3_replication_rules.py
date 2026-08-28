"""S3_BUCKET_REPLICATION_ENABLED — replicate test bucket to logs bucket."""

from __future__ import annotations

import json
import time

import boto3
import pytest
from botocore.exceptions import ClientError

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log
from harness.s3_toggle import S3Toggle


def _dest_name(source: str) -> str:
    if source.startswith("cfg-test-") and not source.startswith("cfg-test-logs-"):
        return "cfg-test-logs-" + source[len("cfg-test-"):]
    return source + "-replica"


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3-bucket-replication-enabled",
        source_identifier="S3_BUCKET_REPLICATION_ENABLED",
        resource_types=["AWS::S3::Bucket"],
        toggle_strategy="s3_replication",
    )


@pytest.mark.s3
@pytest.mark.slow
def test_s3_bucket_replication_enabled(
    s3_test_bucket: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    s3_toggle: S3Toggle,
    aws_region: str,
) -> None:
    dest = _dest_name(s3_test_bucket)
    s3 = boto3.client("s3", region_name=aws_region)
    iam = boto3.client("iam", region_name=aws_region)
    account = boto3.client("sts").get_caller_identity()["Account"]
    role_name = f"harness-s3-repl-{s3_test_bucket[-8:]}"
    role_arn = None
    rule_name = None
    spec = _spec()
    try:
        log(f"===== Testing rule: {spec.rule_name} src={s3_test_bucket} dest={dest} =====")
        for bucket in (s3_test_bucket, dest):
            s3.put_bucket_versioning(
                Bucket=bucket,
                VersioningConfiguration={"Status": "Enabled"},
            )
            log(f"Versioning enabled on {bucket}")

        trust = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "s3.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }],
        }
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetReplicationConfiguration",
                        "s3:ListBucket",
                    ],
                    "Resource": f"arn:aws:s3:::{s3_test_bucket}",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObjectVersionForReplication",
                        "s3:GetObjectVersionAcl",
                        "s3:GetObjectVersionTagging",
                    ],
                    "Resource": f"arn:aws:s3:::{s3_test_bucket}/*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:ReplicateObject",
                        "s3:ReplicateDelete",
                        "s3:ReplicateTags",
                    ],
                    "Resource": f"arn:aws:s3:::{dest}/*",
                },
            ],
        }
        try:
            iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust),
                Description="Harness S3 replication proof",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "EntityAlreadyExists":
                raise
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="repl",
            PolicyDocument=json.dumps(policy),
        )
        role_arn = f"arn:aws:iam::{account}:role/{role_name}"
        time.sleep(8)

        rule_name = config_mgr.put_managed_rule(spec, resource_id=s3_test_bucket)

        try:
            s3.delete_bucket_replication(Bucket=s3_test_bucket)
        except ClientError:
            pass
        s3_toggle._nudge_config_recording("repl-off")
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=s3_test_bucket,
            after_timestamp=change_ts,
            resource_type="AWS::S3::Bucket",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=s3_test_bucket,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=600,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        log(f"Putting replication {s3_test_bucket} -> {dest}")
        s3.put_bucket_replication(
            Bucket=s3_test_bucket,
            ReplicationConfiguration={
                "Role": role_arn,
                "Rules": [{
                    "ID": "harness",
                    "Status": "Enabled",
                    "Priority": 1,
                    "Filter": {"Prefix": ""},
                    "DeleteMarkerReplication": {"Status": "Disabled"},
                    "Destination": {"Bucket": f"arn:aws:s3:::{dest}"},
                }],
            },
        )
        s3_toggle._nudge_config_recording("repl-on")
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=s3_test_bucket,
            after_timestamp=change_ts,
            resource_type="AWS::S3::Bucket",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=s3_test_bucket,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=600,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed replication cycle", style="green")
    finally:
        try:
            s3.delete_bucket_replication(Bucket=s3_test_bucket)
        except Exception:
            pass
        if role_name:
            try:
                iam.delete_role_policy(RoleName=role_name, PolicyName="repl")
            except Exception:
                pass
            try:
                iam.delete_role(RoleName=role_name)
            except Exception as exc:
                log(f"Cleanup role: {exc}", style="yellow")
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
