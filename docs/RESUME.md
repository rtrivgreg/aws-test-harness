# Resume note — aws-test-harness

Last updated: 2026-08-30 04:45 EDT

## Score

Storage CP live **38 / 59**. Partial 1. Parked 8. Catalog-only 12.
Do not apply Terraform drift.

## This morning

Docs caught up to last night's lock of `S3_LAST_BACKUP_RECOVERY_POINT_CREATED`.
Next live attempt: `S3EXPRESS_DIR_BUCKET_LIFECYCLE_RULES_CHECK`
(`tests/test_s3express_lifecycle_rules.py`). Throwaway directory bucket.
No Terraform. Park if Config never discovers `AWS::S3Express::DirectoryBucket`.

## Locked 2026-08-29 evening

- `S3_LAST_BACKUP_RECOVERY_POINT_CREATED` — live across two evals on `cfg-test-ef57dcf4-ca589695`
  - NC before any Backup job
  - C after on-demand S3 Backup job (versioning Enabled for the job only)
  - bucket versioning confirmed **Suspended** again 2026-08-29 17:49

## Locked earlier 2026-08-29 (boto3)

EFS mount-target public, EBS optimized (c3.xlarge + t3.nano),
EFS in-backup-plan, EFS protected-by-plan, S3 protected-by-plan.

## Parked — do not rerun on this recorder

EBS_IN_BACKUP_PLAN (stale vols only); EBS_LAST_BACKUP_RECOVERY_POINT_CREATED (empty results);
RP encrypted; EBS protected-by-plan; snapshot BPA; snapshot C path;
SSE-S3; FSx OpenZFS; RCP.
