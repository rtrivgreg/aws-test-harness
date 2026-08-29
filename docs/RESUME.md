# Resume note — aws-test-harness

Last updated: 2026-08-29 07:46 EDT

## Score

Storage CP live **27 / 59**. Partial 1. Parked **5**. Catalog-only 26.
Do not apply Terraform drift.

## Locked this morning

`EC2_LAUNCH_TEMPLATES_EBS_VOLUME_ENCRYPTED` — 275s NC+C.

## Parked this morning

- `BACKUP_RECOVERY_POINT_ENCRYPTED` — RecoveryPoint inventory []
- `EBS_RESOURCES_PROTECTED_BY_BACKUP_PLAN` — INSUFFICIENT_DATA, results []
- `EBS_SNAPSHOT_BLOCK_PUBLIC_ACCESS` — type exists; CI captured **2025-10-11**;
  disable/enable BPA does not emit a new CI. Do not rerun.

Also: RCP; implicit SSE-S3; FSx OpenZFS; snapshot C path.

## Cleanup

```bash
aws configservice delete-config-rule --region us-east-1 \
  --config-rule-name harness-ebs-snapshot-block-public-access-ef57dcf4
aws ec2 get-snapshot-block-public-access-state --region us-east-1
# expect block-all-sharing
```

## Next

`EFS_FILESYSTEM_CT_ENCRYPTED` (throwaway FS + CMK, boto3 only) if continuing.
Not Backup coverage. Not SnapshotBlockPublicAccess.

```bash
cd ~/repost/aws-test-harness && git pull && source .venv/bin/activate
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
export CATALOG_TABLE_NAME=y62db-config-rule-catalog CATALOG_GROUP=default
export TEST_RUN_ID=ef57dcf4
export S3_TEST_BUCKET=cfg-test-ef57dcf4-ca589695
```

## Terraform

State owns only `module.s3_test_bucket[0].…`. Do not apply.
