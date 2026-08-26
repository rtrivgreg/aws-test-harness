"""
Tag helpers.

Every resource and Config rule created by the harness MUST carry a
``test-run-id`` tag.  This is the primary safety mechanism that allows
safe identification and cleanup.
"""

from __future__ import annotations

import os
import uuid
from typing import Dict


TEST_RUN_ID_TAG_KEY = "test-run-id"
PURPOSE_TAG_KEY = "Purpose"
PURPOSE_TAG_VALUE = "aws-config-rule-testing"


def generate_test_run_id() -> str:
    """Return a new unique test-run-id (short UUID)."""
    return str(uuid.uuid4())[:8]


def get_test_run_id() -> str:
    """
    Resolve the test-run-id for the current process.

    Order of precedence:
    1. Environment variable TEST_RUN_ID
    2. Newly generated short UUID
    """
    return os.environ.get("TEST_RUN_ID") or generate_test_run_id()


def standard_tags(test_run_id: str, extra: Dict[str, str] | None = None) -> Dict[str, str]:
    """Return the canonical tag set that every harness resource must have."""
    tags = {
        TEST_RUN_ID_TAG_KEY: test_run_id,
        PURPOSE_TAG_KEY: PURPOSE_TAG_VALUE,
        "ManagedBy": "aws-config-test-harness",
    }
    if extra:
        tags.update(extra)
    return tags


def assert_has_test_run_id(tags: Dict[str, str] | None, expected_run_id: str) -> None:
    """Raise if the expected test-run-id is missing – used as a safety check."""
    if not tags or tags.get(TEST_RUN_ID_TAG_KEY) != expected_run_id:
        raise RuntimeError(
            f"Resource is missing required tag {TEST_RUN_ID_TAG_KEY}={expected_run_id}. "
            "Refusing to operate on it."
        )
