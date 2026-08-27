# Resume note — aws-test-harness

Last updated: 2026-08-27 17:05 EDT

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited,
SSL-requests-only, logging-enabled. Proven.

**EBS** — `ENCRYPTED_VOLUMES`. Snapshot public-restorable partial only.

**EFS** — encrypted, automatic backups, access points.

**CloudTrail** — log-file validation this host. KMS on the other machine.

**EC2** — IMDSv2, restricted SSH.

**Backup** — min frequency/retention.

## Parked

**restricted-common-ports** — empty evaluations.
**FSx OpenZFS** — Config never discovered the filesystem.
**S3 default encryption** — skip.

## Extra hour

S3 SSL + logging locked. Remaining cheap implemented tests are done.
Optional regression: `pytest tests/test_s3_rules.py -v -s`
Then destroy + stop recorder.
