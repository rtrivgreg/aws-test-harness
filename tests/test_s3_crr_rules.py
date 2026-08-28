"""S3_BUCKET_CROSS_REGION_REPLICATION_ENABLED — us-east-1 test bucket to us-west-2 dest.

Creates and deletes cfg-test-crr-<suffix> in us-west-2. Same-region replication
to the logs bucket is a different identifier (already live).
"""

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

DEST_REGION = "us-west-2"


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3-bucket-cross-region-replication-enabled",
        source_identifier="S3_BUCKET_CROSS_REGION_REPLICATION_ENABLED",
        resource_types=["AWS::S3::Bucket"],
        toggle_strategy="s3_crr",
    )


def _empty_and_delete(s3, bucket: str) -> None:
    try:
        paginator = s3.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=bucket):
            objs = []
            for v in page.get("Versions", []) + page.get("DeleteMarkers", []):
                item = {"Key": v["Key"]}
                if "VersionId" in v:
                    item["VersionId"] = v["VersionId"]
                objs.append(item)
            if objs:
                s3.delete_objects(Bucket=bucket, Delete={"Objects": objs, "Quiet": True})
    except ClientError:
        pass
    try:
        s3.delete_bucket(Bucket=bucket)
        log(f"Deleted dest bucket {bucket}")
    except ClientError as exc:
        log(f"delete dest: {exc}", style="yellow")


@pytest.mark.s3
@pytest.mark.slow
def test_s3_bucket_cross_region_replication_enabled(
    s3_test_bucket: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    s3_toggle: S3Toggle,
    aws_region: str,
) -> None:
    src = boto3.client("s3", region_name=aws_region)
    dest_s3 = boto3.client("s3", region_name=DEST_REGION)
    iam = boto3.client("iam")
    account = boto3.client("sts").get_caller_identity()["Account"]
    dest = f"cfg-test-crr-{s3_test_bucket[-8:]}"
    role_name = f"harness-s3-crr-{s3_test_bucket[-8:]}"
    spec = _spec()
    rule_name = None
    dest_created = False
    try:
        log(f"===== Testing rule: {spec.rule_name} {s3_test_bucket} -> {dest} =====")
        dest_s3.create_bucket(
            Bucket=dest,
            CreateBucketConfiguration={"LocationConstraint": DEST_REGION},
        )
        dest_created = True
        dest_s3.put_bucket_tagging(
            Bucket=dest,
            Tagging={"TagSet": [
                {"Key": "Purpose", "Value": "aws-config-rule-testing"},
                {"Key": "test-run-id", "Value": "ef57dcf4"},
            ]},
        )
        for client, bucket in ((src, s3_test_bucket), (dest_s3, dest)):
            client.put_bucket_versioning(
                Bucket=bucket,
                VersioningConfiguration={"Status": "Enabled"},
            )
        log(f"Dest bucket {dest} in {DEST_REGION}; versioning on both")

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
                    "Action": ["s3:GetReplicationConfiguration", "s3:ListBucket"],
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
                Description="Harness S3 CRR proof",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "EntityAlreadyExists":
                raise
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="crr",
            PolicyDocument=json.dumps(policy),
        )
        role_arn = f"arn:aws:iam::{account}:role/{role_name}"
        time.sleep(8)

        try:
            src.delete_bucket_replication(Bucket=s3_test_bucket)
        except ClientError:
            pass
        rule_name = config_mgr.put_managed_rule(spec, resource_id=s3_test_bucket)
        s3_toggle._nudge_config_recording("crr-off")
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

        log(f"Putting CRR {s3_test_bucket} -> {dest}")
        src.put_bucket_replication(
            Bucket=s3_test_bucket,
            ReplicationConfiguration={
                "Role": role_arn,
                "Rules": [{
                    "ID": "harness-crr",
                    "Status": "Enabled",
                    "Priority": 1,
                    "Filter": {"Prefix": ""},
                    "DeleteMarkerReplication": {"Status": "Disabled"},
                    "Destination": {"Bucket": f"arn:aws:s3:::{dest}"},
                }],
            },
        )
        s3_toggle._nudge_config_recording("crr-on")
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
        log(f"{spec.rule_name} passed CRR cycle", style="green")
    finally:
        try:
            src.delete_bucket_replication(Bucket=s3_test_bucket)
        except Exception:
            pass
        if dest_created:
            _empty_and_delete(dest_s3, dest)
        try:
            iam.delete_role_policy(RoleName=role_name, PolicyName="crr")
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
