# Resume note — aws-test-harness

Last updated: 2026-08-27 17:00 EDT

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited,
`s3-bucket-ssl-requests-only` PASSED 17:00 EDT.

**EBS** — `ENCRYPTED_VOLUMES`. Snapshot public-restorable partial only.

**EFS** — encrypted, automatic backups, access points.

**CloudTrail** — log-file validation this host. KMS on the other machine.

**EC2** — IMDSv2, restricted SSH.

**Backup** — min frequency/retention.

## Parked

**restricted-common-ports** — empty evaluation results.
**FSx OpenZFS** — Config never discovered `AWS::FSx::FileSystem`.
**S3 default encryption** — skip.

## Next

```bash
pytest tests/test_s3_logging_rules.py -v -s
```
