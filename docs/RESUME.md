# Resume note — aws-test-harness

Last updated: 2026-08-27 17:38 EDT

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited,
SSL-requests-only, logging-enabled, **public-read-prohibited** PASSED 17:38 EDT.

**EBS** — `ENCRYPTED_VOLUMES`. Snapshot public-restorable partial only.

**EFS** — encrypted, automatic backups, access points.

**CloudTrail** — log-file validation this host. KMS on the other machine.

**EC2** — IMDSv2, restricted SSH.

**Backup** — min frequency/retention.

## Parked

**restricted-common-ports** — empty evaluations.
**FSx OpenZFS** — Config never discovered the filesystem.
**S3 default encryption** — skip.

## Next optional

`S3_BUCKET_PUBLIC_WRITE_PROHIBITED` (same BPA + policy pattern, PutObject).
Then destroy + stop recorder.
