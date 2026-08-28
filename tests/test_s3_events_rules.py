"""S3_EVENT_NOTIFICATIONS_ENABLED — SQS destination vs empty config.

EventBridge-only is not enough; the managed rule stayed NON_COMPLIANT.
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


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3-event-notifications-enabled",
        source_identifier="S3_EVENT_NOTIFICATIONS_ENABLED",
        resource_types=["AWS::S3::Bucket"],
        toggle_strategy="s3_events",
    )


def _queue_policy(queue_arn: str, bucket: str, account: str) -> str:
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "AllowS3",
            "Effect": "Allow",
            "Principal": {"Service": "s3.amazonaws.com"},
            "Action": "sqs:SendMessage",
            "Resource": queue_arn,
            "Condition": {
                "ArnLike": {"aws:SourceArn": f"arn:aws:s3:::{bucket}"},
                "StringEquals": {"aws:SourceAccount": account},
            },
        }],
    })


@pytest.mark.s3
@pytest.mark.slow
def test_s3_event_notifications_enabled(
    s3_test_bucket: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    s3_toggle: S3Toggle,
    aws_region: str,
) -> None:
    spec = _spec()
    rule_name = None
    sqs = boto3.client("sqs", region_name=aws_region)
    s3 = boto3.client("s3", region_name=aws_region)
    sts = boto3.client("sts", region_name=aws_region)
    account = sts.get_caller_identity()["Account"]
    queue_name = f"harness-s3-events-{s3_test_bucket[-8:]}"
    queue_url = None
    try:
        log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
        created = sqs.create_queue(QueueName=queue_name)
        queue_url = created["QueueUrl"]
        attrs = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])
        queue_arn = attrs["Attributes"]["QueueArn"]
        sqs.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes={"Policy": _queue_policy(queue_arn, s3_test_bucket, account)},
        )
        log(f"SQS destination {queue_arn}")

        rule_name = config_mgr.put_managed_rule(spec, resource_id=s3_test_bucket)

        s3_toggle.make_events_noncompliant()
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

        log(f"Putting SQS ObjectCreated notification on {s3_test_bucket}")
        s3.put_bucket_notification_configuration(
            Bucket=s3_test_bucket,
            NotificationConfiguration={
                "QueueConfigurations": [{
                    "QueueArn": queue_arn,
                    "Events": ["s3:ObjectCreated:*"],
                }]
            },
        )
        s3_toggle._nudge_config_recording("events-sqs")
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
        log(f"{spec.rule_name} passed event-notification cycle", style="green")
    finally:
        try:
            s3_toggle.make_events_noncompliant()
        except Exception as exc:
            log(f"Cleanup notifications: {exc}", style="yellow")
        if queue_url:
            try:
                sqs.delete_queue(QueueUrl=queue_url)
            except ClientError as exc:
                log(f"Cleanup SQS: {exc}", style="yellow")
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
