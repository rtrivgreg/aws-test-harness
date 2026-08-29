# Resume note — aws-test-harness

Last updated: 2026-08-29 08:25 EDT

## Score

Storage CP live **29 / 59**. Partial 1. Parked 5. Catalog-only 24.
Do not apply Terraform drift.

## Locked this morning

- `EC2_LAUNCH_TEMPLATES_EBS_VOLUME_ENCRYPTED`
- `EFS_FILESYSTEM_CT_ENCRYPTED`
- `EC2_EBS_ENCRYPTION_BY_DEFAULT` — 147s; restore enabled=True

## Parked this morning

RP encrypted; EBS protected-by-plan; snapshot BPA stale CI.
Also: RCP; SSE-S3; FSx OpenZFS; snapshot C path.

## Next in flight

`CLOUDTRAIL_ALL_WRITE_S3_DATA_EVENT_CHECK` on existing harness trail.

```bash
cd ~/repost/aws-test-harness && git pull && source .venv/bin/activate
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
export CATALOG_TABLE_NAME=y62db-config-rule-catalog CATALOG_GROUP=default
export TEST_RUN_ID=ef57dcf4
export S3_TEST_BUCKET=cfg-test-ef57dcf4-ca589695
export HARNESS_KEEP_ON_FAIL=1
pytest -q tests/test_cloudtrail_s3_write_data_events.py --tb=short
```
