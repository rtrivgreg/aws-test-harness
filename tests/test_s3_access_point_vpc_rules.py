"""S3_ACCESS_POINT_IN_VPC_ONLY — Internet AP vs VPC AP on the test bucket.

NetworkOrigin cannot change in place; delete and recreate.
"""

from __future__ import annotations

import time

import boto3
import pytest
from botocore.exceptions import ClientError

from harness.catalog import ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log


def _spec() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="s3-access-point-in-vpc-only",
        source_identifier="S3_ACCESS_POINT_IN_VPC_ONLY",
        resource_types=["AWS::S3::AccessPoint"],
        toggle_strategy="s3_ap_vpc",
    )


def _delete_ap(s3c, account: str, name: str) -> None:
    try:
        s3c.delete_access_point(AccountId=account, Name=name)
        log(f"Deleted access point {name}")
        time.sleep(5)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in ("NoSuchAccessPoint", "NoSuchAccessPointException"):
            raise


def _default_vpc_id(region: str) -> str:
    ec2 = boto3.client("ec2", region_name=region)
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])
    ids = [v["VpcId"] for v in vpcs.get("Vpcs", [])]
    if ids:
        return ids[0]
    any_vpcs = ec2.describe_vpcs().get("Vpcs", [])
    if not any_vpcs:
        pytest.skip("No VPC in us-east-1 to attach an access point")
    return any_vpcs[0]["VpcId"]


@pytest.mark.s3
@pytest.mark.slow
def test_s3_access_point_in_vpc_only(
    s3_test_bucket: str,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
    aws_region: str,
) -> None:
    account = boto3.client("sts").get_caller_identity()["Account"]
    s3c = boto3.client("s3control", region_name=aws_region)
    ap_name = f"harness-ap-vpc-{s3_test_bucket[-8:]}"
    vpc_id = _default_vpc_id(aws_region)
    spec = _spec()
    rule_name = None
    created = False
    try:
        log(f"===== Testing rule: {spec.rule_name} vpc={vpc_id} =====")
        _delete_ap(s3c, account, ap_name)
        s3c.create_access_point(
            AccountId=account,
            Name=ap_name,
            Bucket=s3_test_bucket,
        )
        created = True
        log(f"Created Internet-origin AP {ap_name}")

        compliance.wait_for_resource_discovered(
            resource_id=ap_name, resource_type="AWS::S3::AccessPoint"
        )
        rule_name = config_mgr.put_managed_rule(spec, resource_id=ap_name)

        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        nc = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=ap_name,
            expected="NON_COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=600,
        )
        assert nc[0]["ComplianceType"] == "NON_COMPLIANT"

        log(f"Recreating {ap_name} with VpcId={vpc_id}")
        _delete_ap(s3c, account, ap_name)
        created = False
        s3c.create_access_point(
            AccountId=account,
            Name=ap_name,
            Bucket=s3_test_bucket,
            VpcConfiguration={"VpcId": vpc_id},
        )
        created = True
        change_ts = time.time()
        compliance.wait_for_config_item_after(
            resource_id=ap_name,
            after_timestamp=change_ts,
            resource_type="AWS::S3::AccessPoint",
        )
        eval_ts = time.time()
        config_mgr.start_evaluation(rule_name)
        config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)
        c = compliance.wait_for_resource_result(
            rule_name=rule_name,
            resource_id=ap_name,
            expected="COMPLIANT",
            config_mgr=config_mgr,
            after_timestamp=eval_ts,
            timeout_seconds=600,
        )
        assert c[0]["ComplianceType"] == "COMPLIANT"
        log(f"{spec.rule_name} passed VPC-only AP cycle", style="green")
    finally:
        if created:
            try:
                _delete_ap(s3c, account, ap_name)
            except Exception as exc:
                log(f"Cleanup AP: {exc}", style="yellow")
        if rule_name:
            try:
                config_mgr.delete_rule(rule_name)
            except Exception as exc:
                log(f"Cleanup warning: {exc}", style="yellow")
