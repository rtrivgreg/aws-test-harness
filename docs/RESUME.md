# Resume note — aws-test-harness

Last updated: 2026-08-27 15:23 EDT

## Locked live proofs

**S3 full cycle** — versioning, lifecycle, version-lifecycle, public-access prohibited.

**EBS** — `ENCRYPTED_VOLUMES` proven. Snapshot public-restorable partial only.

**EFS** — encrypted, automatic backups, access-point rules. Proven 2026-08-27.

**CloudTrail** — log-file validation PASSED this host. KMS encryption test SKIPPED here
(`CLOUDTRAIL_KMS_KEY_ARN` unset). User reports that slice was done on the other machine.

**S3 skip:** default bucket encryption.

## Next

```bash
git pull
pytest tests/test_ec2_rules.py -v -s
```

IMDSv2. Then SSH / ports if that passes. Defer FSx.
