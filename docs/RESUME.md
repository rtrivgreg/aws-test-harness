# Resume note — aws-test-harness

Last updated: 2026-08-29 08:18 EDT

## Score

Storage CP live **28 / 59**. Partial 1. Parked 5. Catalog-only 25.
Do not apply Terraform drift.

## Locked this morning

- `EC2_LAUNCH_TEMPLATES_EBS_VOLUME_ENCRYPTED` — 275s
- `EFS_FILESYSTEM_CT_ENCRYPTED` — throwaway unenc/enc FS pair, 188s

## Parked this morning

- `BACKUP_RECOVERY_POINT_ENCRYPTED` — RecoveryPoint []
- `EBS_RESOURCES_PROTECTED_BY_BACKUP_PLAN` — INSUFFICIENT_DATA []
- `EBS_SNAPSHOT_BLOCK_PUBLIC_ACCESS` — stale CI 2025-10-11

Also: RCP; implicit SSE-S3; FSx OpenZFS; snapshot C path.

## Next

Still change-triggered, non-coverage. Remaining storage rows are mostly
Backup-family, FSx, account-scoped, or Express One Zone.

```bash
cd ~/repost/aws-test-harness && git pull && source .venv/bin/activate
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
export CATALOG_TABLE_NAME=y62db-config-rule-catalog CATALOG_GROUP=default
export TEST_RUN_ID=ef57dcf4
export S3_TEST_BUCKET=cfg-test-ef57dcf4-ca589695
```

## Terraform

State owns only `module.s3_test_bucket[0].…`. Do not apply.
