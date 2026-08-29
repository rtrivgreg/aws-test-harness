# Resume note — aws-test-harness

Last updated: 2026-08-29 15:24 EDT

## Score

Storage CP live **37 / 59**. Partial 1. Parked 6. Catalog-only 15.
Do not apply Terraform drift.

## Locked after the break

- `S3_RESOURCES_PROTECTED_BY_BACKUP_PLAN` — 127s; live bucket off-plan NC / on-plan C
  - bucket `cfg-test-ef57dcf4-ca589695`
  - plan `b6cddd41-80ff-41e1-88da-7fccc3bab8fc` deleted; bucket kept

## Locked earlier today (boto3)

- `EFS_MOUNT_TARGET_PUBLIC_ACCESSIBLE`
- `EBS_OPTIMIZED_INSTANCE` (c3.xlarge + t3.nano)
- `EFS_IN_BACKUP_PLAN`
- `EFS_RESOURCES_PROTECTED_BY_BACKUP_PLAN`

## Parked

RP encrypted; EBS protected-by-plan; snapshot BPA stale CI;
RCP; SSE-S3; FSx OpenZFS; snapshot C path.

## Next least-bad

`EBS_IN_BACKUP_PLAN` — same boto3 volume+plan pattern as EFS_IN_BACKUP_PLAN.
EBS *protected-by-plan* is still parked; this identifier may differ.
