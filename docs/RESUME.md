# Resume note — aws-test-harness

Last updated: 2026-08-27 14:55 EDT

Source of truth: git on `main`, not the chat history.

## Locked live proofs (ran against Config and documented)

**S3 full cycle**
- `S3_BUCKET_VERSIONING_ENABLED`
- `S3_LIFECYCLE_POLICY_CHECK`
- `S3_VERSION_LIFECYCLE_POLICY_CHECK`
- `S3_BUCKET_LEVEL_PUBLIC_ACCESS_PROHIBITED`

**EBS**
- `ENCRYPTED_VOLUMES` — two attached volumes. Proven.
- `EBS_SNAPSHOT_PUBLIC_RESTORABLE_CHECK` — **partial.** Periodic + account-scoped.
  Do not keep re-running in a shared account.

**EFS**
- `EFS_ENCRYPTED_CHECK` — two file systems. Proven 2026-08-27
  (`fs-00758a1a702fe85fd` COMPLIANT; unencrypted NON_COMPLIANT;
  rule `harness-efs-encrypted-check-14ac09fc`).

**S3 skip:** `S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED` — default AES256.

## Implemented, not yet re-locked this afternoon

| Family | Tests | Next |
|--------|--------|------|
| EFS more | `test_efs_backup_rules.py`, `test_efs_access_point_rules.py` | Same FS session if still up |
| CloudTrail | validation + KMS | After EFS extras |
| EC2 | IMDSv2, SSH, ports | Need subnet |
| FSx | OpenZFS | Defer (cost / time) |
| Backup | min frequency / retention | Later |
| S3 extra | SSL, access-logging | Later |

## Suggested next run

Same Terraform EFS resources if they still exist:

```bash
pytest tests/test_efs_backup_rules.py -v -s
```

Then `tests/test_efs_access_point_rules.py`.

## Hygiene

Destroy Terraform at end of session. Delete leftover `harness-*` rules.
Stop the customer managed recorder when idle. Fresh `TEST_RUN_ID` per machine.
