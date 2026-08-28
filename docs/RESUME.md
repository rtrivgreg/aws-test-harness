# Resume note — aws-test-harness

Last updated: 2026-08-28 08:34 EDT

## Score

Grade this iteration: **D** (FSx AVAILABLE; Config CI never appeared).
Portfolio live proofs: **21 / 26 = 81%**.
Session grade: **B+**.

## Locked live proofs (21)

**S3 (10)** versioning, lifecycle, version-lifecycle, public-access,
SSL, logging, public-read, public-write, ACL prohibited,
S3_DEFAULT_ENCRYPTION_KMS.

**EBS (1)** ENCRYPTED_VOLUMES.

**EFS (3)** encrypted, backups, access points.

**CloudTrail (1)** log-file validation.

**EC2 (3)** IMDSv2, restricted SSH, vpc-sg-port-restriction-check.

**Backup (1)** min frequency/retention.

## Parked

**FSx / FSX_OPENZFS_COPY_TAGS_ENABLED** — `fs-0e541e6d001fad3d9` AVAILABLE,
`list-discovered-resources` empty, GetResourceConfigHistory
ResourceNotDiscoveredException after 26 min. Do not rerun.
Destroy the filesystem.

RESTRICTED_INCOMING_TRAFFIC (INSUFFICIENT_DATA).
S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED (platform default SSE).
EBS snapshot public-restorable (NC proven; C account-scoped xfail).
CloudTrail KMS (other machine).
