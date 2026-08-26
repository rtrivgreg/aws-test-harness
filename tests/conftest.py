"""
pytest fixtures for the AWS Config rule test harness.

Session-scoped fixtures keep the expensive Terraform resource alive for
the whole test run.  Function-scoped fixtures give each test a clean
Config rule lifecycle.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Generator

import pytest

from harness.catalog import CatalogClient, ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import set_dry_run, log
from harness.s3_toggle import S3Toggle
from harness.tags import get_test_run_id


# ---------------------------------------------------------------------------
# Command-line options
# ---------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print actions instead of calling mutating AWS APIs",
    )
    parser.addoption(
        "--test-run-id",
        action="store",
        default=None,
        help="Override the test-run-id (otherwise taken from env or generated)",
    )
    parser.addoption(
        "--terraform-dir",
        action="store",
        default="terraform",
        help="Path to the Terraform root module",
    )


@pytest.fixture(scope="session", autouse=True)
def _configure_dry_run(request: pytest.FixtureRequest) -> None:
    enabled = request.config.getoption("--dry-run")
    set_dry_run(enabled)
    if enabled:
        log("Dry-run mode ENABLED – no mutating AWS calls will be made", style="yellow")


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


# ---------------------------------------------------------------------------
# Terraform-provisioned S3 bucket
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def s3_test_bucket(test_run_id: str, aws_region: str, request: pytest.FixtureRequest) -> Generator[str, None, None]:
    """
    Ensure the minimal S3 test bucket exists (via Terraform) and yield its name.
    The bucket is left in place after the run so it can be inspected; destroy
    it explicitly with `terraform destroy` when finished.
    """
    tf_dir = Path(request.config.getoption("--terraform-dir"))
    if not tf_dir.exists():
        pytest.skip(f"Terraform directory {tf_dir} not found")

    # Apply (or refresh) the S3 module
    log("Running terraform apply for S3 test bucket …")
    env = os.environ.copy()
    env["TF_VAR_test_run_id"] = test_run_id
    env["TF_VAR_aws_region"] = aws_region

    # We use -auto-approve for CI friendliness; users can still run plan manually
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

    # Read the output
    out = subprocess.run(
        ["terraform", "output", "-json"],
        cwd=tf_dir,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    outputs = json.loads(out.stdout)
    bucket_name = outputs.get("s3_test_bucket_name", {}).get("value")
    if not bucket_name:
        pytest.fail("terraform output s3_test_bucket_name is empty")

    log(f"S3 test bucket ready: {bucket_name}")
    yield bucket_name
    # Intentionally no destroy here – leave the resource for inspection / reuse


# ---------------------------------------------------------------------------
# Catalog + managers
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def catalog() -> CatalogClient:
    return CatalogClient()


@pytest.fixture(scope="session")
def s3_rules(catalog: CatalogClient) -> list[ManagedRuleSpec]:
    """All S3-related rules from the live DynamoDB catalog."""
    rules = catalog.list_rules_for_group(family="s3")
    if not rules:
        log(
            "No S3 rules returned from catalog – tests will be skipped. "
            "Check CATALOG_TABLE_NAME / CATALOG_GROUP and the scan filter.",
            style="yellow",
        )
    return rules


@pytest.fixture
def config_mgr(test_run_id: str, aws_region: str) -> ConfigRuleManager:
    return ConfigRuleManager(region=aws_region, test_run_id=test_run_id)


@pytest.fixture
def compliance(aws_region: str) -> ComplianceChecker:
    return ComplianceChecker(region=aws_region)


@pytest.fixture
def s3_toggle(s3_test_bucket: str, aws_region: str) -> S3Toggle:
    return S3Toggle(bucket_name=s3_test_bucket, region=aws_region)
