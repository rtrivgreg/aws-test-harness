"""
EBS vertical slice v1 – ENCRYPTED_VOLUMES.

Unlike S3, EBS encryption cannot be flipped on an existing volume.
Terraform creates two attached 1 GiB volumes; we assert each id.
"""

from __future__ import annotations

import os
import time

import pytest

from harness.catalog import CatalogClient, ManagedRuleSpec
from harness.compliance import ComplianceChecker
from harness.config_rule import ConfigRuleManager
from harness.dry_run import log

DEFAULT_ALLOWLIST = {
    "ENCRYPTED_VOLUMES",
    "encrypted-volumes",
    "RULE#encrypted-volumes",
}


def _is_allowed(spec: ManagedRuleSpec) -> bool:
    if os.environ.get("ALLOW_ALL_EBS_RULES") == "1":
        return True
    return (
        spec.source_identifier in DEFAULT_ALLOWLIST
        or spec.rule_name in DEFAULT_ALLOWLIST
        or "encrypted-volumes" in spec.rule_name.lower()
        or spec.source_identifier == "ENCRYPTED_VOLUMES"
    )


def _synthetic_encrypted_volumes() -> ManagedRuleSpec:
    return ManagedRuleSpec(
        rule_name="encrypted-volumes",
        source_identifier="ENCRYPTED_VOLUMES",
        input_parameters={},
        resource_types=["AWS::EC2::Volume"],
        description="Harness fallback if catalog has no EBS rows",
        toggle_strategy="ebs_two_volume",
    )


@pytest.mark.ebs
@pytest.mark.slow
def test_ebs_encrypted_volumes_cycle(
    ebs_volumes: dict,
    catalog: CatalogClient,
    config_mgr: ConfigRuleManager,
    compliance: ComplianceChecker,
) -> None:
    rules = catalog.list_rules_for_group(family="ebs")
    # Catalog family filter is name-based; also pull encrypted-volumes from a full scan
    if not any(_is_allowed(r) for r in rules):
        rules = catalog.list_rules_for_group(family=None)
    selected = [r for r in rules if _is_allowed(r)]
    if not selected:
        log("Catalog has no ENCRYPTED_VOLUMES row – using synthetic spec")
        selected = [_synthetic_encrypted_volumes()]

    unenc = ebs_volumes["unencrypted_volume_id"]
    enc = ebs_volumes["encrypted_volume_id"]
    log(f"EBS unencrypted={unenc} encrypted={enc}")

    failures: list[str] = []
    for spec in selected:
        rule_name = None
        try:
            log(f"===== Testing rule: {spec.rule_name} ({spec.source_identifier}) =====")
            rule_name = config_mgr.put_managed_rule(spec)
            eval_ts = time.time()
            config_mgr.start_evaluation(rule_name)
            config_mgr.wait_for_evaluation(rule_name, after_timestamp=eval_ts)

            compliance.assert_resource_compliance(
                rule_name=rule_name,
                resource_id=unenc,
                expected="NON_COMPLIANT",
                resource_type="AWS::EC2::Volume",
                config_mgr=config_mgr,
                after_timestamp=eval_ts,
            )
            compliance.assert_resource_compliance(
                rule_name=rule_name,
                resource_id=enc,
                expected="COMPLIANT",
                resource_type="AWS::EC2::Volume",
                config_mgr=config_mgr,
                after_timestamp=eval_ts,
            )
            log(f"✓ {spec.rule_name} passed EBS two-volume cycle", style="green")
        except Exception as exc:
            failures.append(f"{spec.rule_name}: {exc}")
            log(f"✗ {spec.rule_name} failed: {exc}", style="red")
        finally:
            if rule_name:
                try:
                    config_mgr.delete_rule(rule_name)
                except Exception as cleanup_exc:
                    log(f"Cleanup warning for {rule_name}: {cleanup_exc}", style="yellow")

    if failures:
        pytest.fail(
            f"{len(failures)} EBS rule(s) failed:\n" + "\n".join(failures)
        )
