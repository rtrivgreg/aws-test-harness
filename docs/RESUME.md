# Resume note — aws-test-harness

Last updated: 2026-08-29 07:35 EDT

## Score

Storage CP live **27 / 59**. Partial 1. Parked 4. Catalog-only 27.
Portfolio standing proofs **33** (32 + LT encryption).
Do not apply Terraform drift.

## Locked this morning

`EC2_LAUNCH_TEMPLATES_EBS_VOLUME_ENCRYPTED` — throwaway LT default version
Encrypted=false NC, Encrypted=true C. pytest 275s. Template deleted in finally.

## Parked this morning

- `BACKUP_RECOVERY_POINT_ENCRYPTED` — Config RecoveryPoint []
- `EBS_RESOURCES_PROTECTED_BY_BACKUP_PLAN` — INSUFFICIENT_DATA, results []

Also: RCP; implicit SSE-S3; FSx OpenZFS; snapshot C path.

## Backend

tfstate versioning Enabled. Lock ACTIVE. Recorder on.
Live bucket `cfg-test-ef57dcf4-ca589695` versioning Suspended.

## Next

Change-triggered, non-Backup-coverage. Candidate:
`EBS_SNAPSHOT_BLOCK_PUBLIC_ACCESS` (region setting) or
`EFS_FILESYSTEM_CT_ENCRYPTED` if a CMK-toggle is acceptable.

```bash
cd ~/repost/aws-test-harness && git pull && source .venv/bin/activate
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
export CATALOG_TABLE_NAME=y62db-config-rule-catalog CATALOG_GROUP=default
export TEST_RUN_ID=ef57dcf4
export S3_TEST_BUCKET=cfg-test-ef57dcf4-ca589695
```

## Terraform

State owns only `module.s3_test_bucket[0].…`. EC2 only. Do not apply.
