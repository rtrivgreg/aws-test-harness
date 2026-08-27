# Resume note — aws-test-harness

Last updated: 2026-08-27 15:01 EDT

Source of truth: git on `main`, not the chat history.

## Locked live proofs

**S3 full cycle**
- `S3_BUCKET_VERSIONING_ENABLED`
- `S3_LIFECYCLE_POLICY_CHECK`
- `S3_VERSION_LIFECYCLE_POLICY_CHECK`
- `S3_BUCKET_LEVEL_PUBLIC_ACCESS_PROHIBITED`

**EBS**
- `ENCRYPTED_VOLUMES` — proven.
- `EBS_SNAPSHOT_PUBLIC_RESTORABLE_CHECK` — partial only. Do not re-run in a shared account.

**EFS**
- `EFS_ENCRYPTED_CHECK` — proven 2026-08-27.
- `EFS_AUTOMATIC_BACKUPS_ENABLED` (harness-efs-automatic-backups-enabled-14ac09fc) — proven 2026-08-27.

**S3 skip:** `S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED` — default AES256.

## Next

```bash
git pull
pytest tests/test_efs_access_point_rules.py -v -s
```

Then CloudTrail validation. Defer FSx.

## Hygiene

Destroy Terraform at end of session. Delete leftover `harness-*` rules.
Stop recorder when idle.
