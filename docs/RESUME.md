# Resume note — aws-test-harness

Last updated: 2026-08-27 15:18 EDT

Source of truth: git on `main`.

## Locked live proofs

**S3 full cycle** — versioning, lifecycle, version-lifecycle, public-access prohibited.

**EBS** — `ENCRYPTED_VOLUMES` proven. Snapshot public-restorable partial only.

**EFS** — encrypted, automatic backups, access-point rules. Proven 2026-08-27.

**CloudTrail** — `test_cloudtrail_rules.py` (log-file validation toggle). PASSED 15:18 EDT.

**S3 skip:** default bucket encryption.

## Next

```bash
git pull
pytest tests/test_cloudtrail_encryption_rules.py -v -s
```

Then EC2 IMDSv2 or SSH. Defer FSx.
