"""
Catalog client – reads managed-rule definitions and group bindings
from the DynamoDB table that backs aws-crud-rules-db / cpgNG.py.

The exact table schema is expected to evolve; this module isolates
that knowledge so the rest of the harness stays stable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from harness.dry_run import log


@dataclass
class ManagedRuleSpec:
    """Canonical representation of a managed rule as needed by the harness."""

    rule_name: str                          # human / Config rule name
    source_identifier: str                  # e.g. S3_BUCKET_VERSIONING_ENABLED
    input_parameters: Dict[str, str] = field(default_factory=dict)
    resource_types: List[str] = field(default_factory=list)
    description: str = ""
    # Optional metadata for the toggle logic
    toggle_strategy: str = "s3_generic"     # maps to a function in s3_toggle.py


class CatalogClient:
    """
    Thin wrapper around the DynamoDB catalog.

    Expected environment / settings:
      - CATALOG_TABLE_NAME   (required)
      - CATALOG_GROUP        (optional – which organizational binding to use)
      - AWS_REGION
    """

    def __init__(
        self,
        table_name: Optional[str] = None,
        group: Optional[str] = None,
        region: Optional[str] = None,
    ) -> None:
        self.table_name = table_name or os.environ.get("CATALOG_TABLE_NAME")
        if not self.table_name:
            raise ValueError(
                "CATALOG_TABLE_NAME must be set (env var or constructor argument)"
            )
        self.group = group or os.environ.get("CATALOG_GROUP", "default")
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")

        self._ddb = boto3.resource("dynamodb", region_name=self.region)
        self._table = self._ddb.Table(self.table_name)

    def list_rules_for_group(self, family: Optional[str] = None) -> List[ManagedRuleSpec]:
        """
        Return all managed rules that belong to the configured group,
        optionally filtered by family (e.g. "s3", "ebs").

        NOTE: The concrete query pattern depends on the final schema of
        the DynamoDB table.  The implementation below is deliberately
        conservative and should be adjusted once the real key design is
        confirmed.
        """
        log(f"Loading rules from catalog table={self.table_name} group={self.group}")

        # Placeholder scan – replace with a Query once the GSI / key schema
        # for group bindings is finalized.
        try:
            response = self._table.scan()
            items = response.get("Items", [])
            while "LastEvaluatedKey" in response:
                response = self._table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
                items.extend(response.get("Items", []))
        except ClientError as exc:
            raise RuntimeError(f"Failed to read catalog table: {exc}") from exc

        rules: List[ManagedRuleSpec] = []
        for item in items:
            # Very defensive mapping – adjust attribute names to match reality
            rule_name = item.get("rule_name") or item.get("RuleName") or item.get("pk")
            source_id = item.get("source_identifier") or item.get("SourceIdentifier")
            if not rule_name or not source_id:
                continue

            # Simple family filter based on naming convention
            if family and family.lower() not in rule_name.lower():
                continue

            params = item.get("input_parameters") or item.get("InputParameters") or {}
            if isinstance(params, str):
                # some loaders store JSON strings
                import json
                try:
                    params = json.loads(params)
                except Exception:
                    params = {}

            rules.append(
                ManagedRuleSpec(
                    rule_name=rule_name,
                    source_identifier=source_id,
                    input_parameters={str(k): str(v) for k, v in params.items()},
                    resource_types=item.get("resource_types") or item.get("ResourceTypes") or [],
                    description=item.get("description") or "",
                    toggle_strategy=item.get("toggle_strategy", "s3_generic"),
                )
            )

        log(f"Catalog returned {len(rules)} rule(s) for group={self.group}")
        return rules

    def get_rule(self, rule_name: str) -> Optional[ManagedRuleSpec]:
        """Fetch a single rule by name (convenience wrapper)."""
        for rule in self.list_rules_for_group():
            if rule.rule_name == rule_name:
                return rule
        return None
