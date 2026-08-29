# Resume note — aws-test-harness

Last updated: 2026-08-29 08:41 EDT

## Score

Storage CP live **31 / 59**. Partial 1. Parked 5. Catalog-only 22.
Do not apply Terraform drift.

## Locked this morning (5)

- `EC2_LAUNCH_TEMPLATES_EBS_VOLUME_ENCRYPTED`
- `EFS_FILESYSTEM_CT_ENCRYPTED`
- `EC2_EBS_ENCRYPTION_BY_DEFAULT`
- `CLOUDTRAIL_ALL_WRITE_S3_DATA_EVENT_CHECK`
- `CLOUDTRAIL_ALL_READ_S3_DATA_EVENT_CHECK` — 148s

## Parked this morning (3)

RP encrypted; EBS protected-by-plan; snapshot BPA stale CI.
Also earlier: RCP; SSE-S3; FSx OpenZFS; snapshot C path.

## Next

Remaining storage catalog-only is Backup-family, FSx, S3 Express, MFA-delete,
air-gapped vault, restore-time, mount-target, spot-fleet. Thinner odds.
Natural stop. Do not apply Terraform.

```bash
cd ~/repost/aws-test-harness && git pull && source .venv/bin/activate
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
export CATALOG_TABLE_NAME=y62db-config-rule-catalog CATALOG_GROUP=default
export TEST_RUN_ID=ef57dcf4
export S3_TEST_BUCKET=cfg-test-ef57dcf4-ca589695
```
