"""pytest fixtures for the AWS Config rule test harness."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Generator

import pytest

from harness.catalog import CatalogClient, ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import set_dry_run, log
from harness.s3_toggle import S3Toggle
from harness.tags import get_test_run_id


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--dry-run", action="store_true", default=False)
    parser.addoption("--test-run-id", action="store", default=None)
    parser.addoption("--terraform-dir", action="store", default="terraform")


@pytest.fixture(scope="session", autouse=True)
def _configure_dry_run(request: pytest.FixtureRequest) -> None:
    enabled = request.config.getoption("--dry-run")
    set_dry_run(enabled)
    if enabled:
        log("Dry-run mode ENABLED", style="yellow")


@pytest.fixture(scope="session")
def test_run_id(request: pytest.FixtureRequest) -> str:
    cli_value = request.config.getoption("--test-run-id")
    if cli_value:
        os.environ["TEST_RUN_ID"] = cli_value
        return cli_value
    rid = get_test_run_id()
    os.environ["TEST_RUN_ID"] = rid
    log(f"Using test-run-id = {rid}")
    return rid


@pytest.fixture(scope="session")
def aws_region() -> str:
    return os.environ.get("AWS_REGION", "us-east-1")


def _terraform_apply(tf_dir: Path, env: dict) -> dict:
    init = subprocess.run(
        ["terraform", "init", "-input=false"],
        cwd=tf_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    if init.returncode != 0:
        log(init.stderr, style="red")
        pytest.fail(f"terraform init failed: {init.stderr}")
    result = subprocess.run(
        ["terraform", "apply", "-auto-approve", "-input=false"],
        cwd=tf_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log(result.stderr, style="red")
        pytest.fail(f"terraform apply failed: {result.stderr}")
    out = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=tf_dir,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


@pytest.fixture(scope="session")
def s3_test_bucket(
    test_run_id: str, aws_region: str, request: pytest.FixtureRequest
) -> Generator[str, None, None]:
    tf_dir = Path(request.config.getoption("--terraform-dir"))
    if not tf_dir.exists():
        pytest.skip(f"Terraform directory {tf_dir} not found")
    env = os.environ.copy()
    env["TF_VAR_test_run_id"] = test_run_id
    env["TF_VAR_aws_region"] = aws_region
    outputs = _terraform_apply(tf_dir, env)
    bucket_name = outputs.get("s3_test_bucket_name", {}).get("value")
    if not bucket_name:
        pytest.fail("terraform output s3_test_bucket_name is empty")
    log(f"S3 test bucket ready: {bucket_name}")
    ComplianceChecker(region=aws_region).wait_for_resource_discovered(
        resource_id=bucket_name, resource_type="AWS::S3::Bucket"
    )
    yield bucket_name


@pytest.fixture(scope="session")
def ebs_volumes(
    test_run_id: str, aws_region: str, request: pytest.FixtureRequest
) -> Generator[dict, None, None]:
    tf_dir = Path(request.config.getoption("--terraform-dir"))
    env = os.environ.copy()
    env["TF_VAR_test_run_id"] = test_run_id
    env["TF_VAR_aws_region"] = aws_region
    env["TF_VAR_enable_ebs_test_volumes"] = "true"
    outputs = _terraform_apply(tf_dir, env)
    unenc = outputs.get("ebs_unencrypted_volume_id", {}).get("value")
    enc = outputs.get("ebs_encrypted_volume_id", {}).get("value")
    snap = outputs.get("ebs_unencrypted_snapshot_id", {}).get("value")
    inst = outputs.get("ebs_instance_id", {}).get("value")
    if not unenc or not enc:
        pytest.fail("terraform EBS volume outputs are empty")
    checker = ComplianceChecker(region=aws_region)
    checker.wait_for_resource_discovered(unenc, "AWS::EC2::Volume")
    checker.wait_for_resource_discovered(enc, "AWS::EC2::Volume")
    yield {
        "instance_id": inst,
        "unencrypted_volume_id": unenc,
        "encrypted_volume_id": enc,
        "unencrypted_snapshot_id": snap,
    }


@pytest.fixture(scope="session")
def efs_filesystems(
    test_run_id: str, aws_region: str, request: pytest.FixtureRequest
) -> Generator[dict, None, None]:
    tf_dir = Path(request.config.getoption("--terraform-dir"))
    env = os.environ.copy()
    env["TF_VAR_test_run_id"] = test_run_id
    env["TF_VAR_aws_region"] = aws_region
    env["TF_VAR_enable_efs_test_filesystems"] = "true"
    log("Running terraform apply for EFS test file systems ...")
    outputs = _terraform_apply(tf_dir, env)
    unenc = outputs.get("efs_unencrypted_id", {}).get("value")
    enc = outputs.get("efs_encrypted_id", {}).get("value")
    ap_nc = outputs.get("efs_access_point_nc_id", {}).get("value")
    ap_c = outputs.get("efs_access_point_c_id", {}).get("value")
    if not unenc or not enc:
        pytest.fail("terraform EFS outputs are empty")
    checker = ComplianceChecker(region=aws_region)
    checker.wait_for_resource_discovered(unenc, "AWS::EFS::FileSystem")
    checker.wait_for_resource_discovered(enc, "AWS::EFS::FileSystem")
    if ap_nc:
        checker.wait_for_resource_discovered(ap_nc, "AWS::EFS::AccessPoint")
    if ap_c:
        checker.wait_for_resource_discovered(ap_c, "AWS::EFS::AccessPoint")
    yield {
        "unencrypted_id": unenc,
        "encrypted_id": enc,
        "access_point_nc_id": ap_nc,
        "access_point_c_id": ap_c,
    }


@pytest.fixture(scope="session")
def cloudtrail_trail(
    test_run_id: str, aws_region: str, request: pytest.FixtureRequest
) -> Generator[dict, None, None]:
    tf_dir = Path(request.config.getoption("--terraform-dir"))
    env = os.environ.copy()
    env["TF_VAR_test_run_id"] = test_run_id
    env["TF_VAR_aws_region"] = aws_region
    env["TF_VAR_enable_cloudtrail_test"] = "true"
    log("Running terraform apply for CloudTrail test trail ...")
    outputs = _terraform_apply(tf_dir, env)
    name = outputs.get("cloudtrail_name", {}).get("value")
    arn = outputs.get("cloudtrail_arn", {}).get("value")
    if not name:
        pytest.fail("terraform cloudtrail_name output is empty")
    log(f"CloudTrail ready: {name}")
    ComplianceChecker(region=aws_region).wait_for_resource_discovered(
        name, "AWS::CloudTrail::Trail"
    )
    yield {"trail_name": name, "trail_arn": arn}


@pytest.fixture(scope="session")
def catalog() -> CatalogClient:
    return CatalogClient()


@pytest.fixture(scope="session")
def s3_rules(catalog: CatalogClient) -> list[ManagedRuleSpec]:
    return catalog.list_rules_for_group(family="s3")


@pytest.fixture
def config_mgr(test_run_id: str, aws_region: str) -> ConfigRuleManager:
    return ConfigRuleManager(region=aws_region, test_run_id=test_run_id)


@pytest.fixture
def compliance(aws_region: str) -> ComplianceChecker:
    return ComplianceChecker(region=aws_region)


@pytest.fixture
def s3_toggle(s3_test_bucket: str, aws_region: str) -> S3Toggle:
    return S3Toggle(bucket_name=s3_test_bucket, region=aws_region)
