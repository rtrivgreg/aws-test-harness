# Resume note — aws-test-harness

Last updated: 2026-08-29 17:49 EDT

## Score

Storage CP live **38 / 59**. Partial 1. Parked 8. Catalog-only 12.
Do not apply Terraform drift.

## Locked this evening

- `S3_LAST_BACKUP_RECOVERY_POINT_CREATED` — live across two evals on `cfg-test-ef57dcf4-ca589695`
  - NC before any Backup job
  - C after on-demand S3 Backup job (versioning Enabled for the job only)
  - bucket versioning confirmed **Suspended** again 2026-08-29 17:49
  - later single-process rerun stayed C because the RP was still inside the 1h window; do not rerun tonight

## Locked earlier today (boto3)

EFS mount-target public, EBS optimized (c3.xlarge + t3.nano),
EFS in-backup-plan, EFS protected-by-plan, S3 protected-by-plan.

## Parked today

EBS_IN_BACKUP_PLAN (stale vols only); EBS_LAST_BACKUP_RECOVERY_POINT_CREATED (empty results);
plus earlier RP encrypted, EBS protected-by-plan, snapshot BPA, RCP, SSE-S3, FSx OpenZFS, snapshot C.
