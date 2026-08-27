# Resume note — aws-test-harness

Last updated: 2026-08-27 15:07 EDT

Source of truth: git on `main`.

## Locked live proofs

**S3 full cycle** — versioning, lifecycle, version-lifecycle, bucket-level public access prohibited.

**EBS** — `ENCRYPTED_VOLUMES` proven. Snapshot public-restorable partial only.

**EFS** (2026-08-27)
- `EFS_ENCRYPTED_CHECK`
- `EFS_AUTOMATIC_BACKUPS_ENABLED`
- access-point rules (`test_efs_access_point_rules.py`) — PASSED 15:07 EDT

**S3 skip:** server-side encryption default AES256.

## Next

EFS family representative slice is locked. Next cheapest non-FSx proof:

```bash
git pull
pytest tests/test_cloudtrail_rules.py -v -s
```

Defer FSx. Destroy EFS resources when you leave the EFS session if CloudTrail uses a separate apply.
