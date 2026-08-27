# Resume note — aws-test-harness

Last updated: 2026-08-27 17:56 EDT — session closed.

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited,
SSL, logging, public-read, public-write.

**EBS** — ENCRYPTED_VOLUMES. Snapshot public-restorable partial.

**EFS** — encrypted, backups, access points.

**CloudTrail** — log-file validation (KMS on other machine).

**EC2** — IMDSv2, restricted SSH.

**Backup** — min frequency/retention.

## Not locked

**S3_BUCKET_ACL_PROHIBITED** — FAILED 17:52. Config *did* evaluate
`cfg-test-14ac09fc-68e6193a` and left it COMPLIANT. Ownership-only toggle is
not enough. Fix pushed: relax BPA + `ACL=public-read`, then Enforced + private.
Re-run tomorrow: `pytest tests/test_s3_acl_rules.py -v -s`

## Parked

ports (empty evals), FSx (not discovered), S3 default encryption.
