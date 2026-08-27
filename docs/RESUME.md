# Resume note — aws-test-harness

Last updated: 2026-08-27 17:54 EDT — session closed.

Source of truth: this file + git `main`. Do not replay locked proofs.

## Locked live proofs

**S3**
- versioning, lifecycle, version-lifecycle
- bucket-level public access prohibited
- SSL-requests-only
- logging-enabled
- public-read-prohibited
- public-write-prohibited

**EBS** — `ENCRYPTED_VOLUMES` (two volumes). Snapshot public-restorable = partial only.

**EFS** — encrypted, automatic backups, access points.

**CloudTrail** — log-file validation on this host. KMS encryption done on the other machine.

**EC2** — IMDSv2, restricted SSH.

**Backup** — min frequency / retention.

## Last command (not locked here)

`pytest tests/test_s3_acl_rules.py -v -s`
(`S3_BUCKET_ACL_PROHIBITED`, ownership BucketOwnerPreferred vs Enforced).
Result was not pasted into the closing chat. Confirm PASSED before treating as locked.

## Parked

- `RESTRICTED_INCOMING_TRAFFIC` / restricted-common-ports — empty evaluations.
- FSx OpenZFS — filesystem created; Config `ResourceNotDiscoveredException`.
- `S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED` — default AES256.

## Tomorrow

1. `git pull` and read this file.
2. If ACL passed, mark it locked; else re-run that one test.
3. Do not chase FSx or ports unless asked.
4. Next product work: another S3 rule, or a conformance-pack-level evaluation — not a new family.

## Hygiene

Destroy Terraform leftovers. Stop the customer managed recorder when idle.
