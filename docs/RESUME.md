# Resume note — aws-test-harness

Last updated: 2026-08-29 15:56 EDT

## Score

Storage CP live **37 / 59**. Partial 1. Parked 7. Catalog-only 14.
Do not apply Terraform drift.

## Locked after the break

- `S3_RESOURCES_PROTECTED_BY_BACKUP_PLAN` — 127s
- `EFS_IN_BACKUP_PLAN` / `EFS_RESOURCES_PROTECTED_BY_BACKUP_PLAN` earlier

## Parked this afternoon — EBS_IN_BACKUP_PLAN

Rule ACTIVE and emitting results, but only for leftover volumes:

- `vol-02fb846068d4f8138` NON_COMPLIANT
- `vol-060b48b8621c69275` NON_COMPLIANT

Harness volumes never appeared: `vol-09c267fad47044590`, then `vol-035c6b510dbfd949f`.
Three evals / 300s+. Do not rerun. EFS/S3 twins of this family are live.

Also parked earlier: RP encrypted; EBS protected-by-plan; snapshot BPA stale CI;
RCP; SSE-S3; FSx OpenZFS; snapshot C path.
