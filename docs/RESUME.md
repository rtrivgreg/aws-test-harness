# Resume note — aws-test-harness

Last updated: 2026-08-27

## Locked proofs

**S3 (full cycle):**
- `S3_BUCKET_VERSIONING_ENABLED`
- `S3_LIFECYCLE_POLICY_CHECK`
- `S3_VERSION_LIFECYCLE_POLICY_CHECK`
- `S3_BUCKET_LEVEL_PUBLIC_ACCESS_PROHIBITED`

**EBS:**
- `ENCRYPTED_VOLUMES` — full cycle (two attached volumes). Proven.
- `EBS_SNAPSHOT_PUBLIC_RESTORABLE_CHECK` — **partial.** Periodic + account-scoped.
  NON_COMPLIANT proven when harness snapshot is public. COMPLIANT not isolatable
  if any other snapshot in the account is public (Config reports
  `AWS::::Account`, annotation `Public Amazon EBS Snapshots: N`).
  Do not keep re-running this rule in a shared account.

**S3 skip:** `S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED` — default encryption.

## In flight

EFS vertical slice: two file systems (encrypted / not) + `EFS_ENCRYPTED_CHECK`.

## Recorder / cost / EC2

Stop customer managed recorder when idle (no penalty). Start before tests.
Local Terraform state per machine is fine. Destroy after the session.
