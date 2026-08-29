# Resume note — aws-test-harness

Last updated: 2026-08-29 13:50 EDT

## Score

Storage CP live **34 / 59**. Partial 1. Parked 6. Catalog-only 18.
Do not apply Terraform drift.

## Runner disk (t3.medium)

```bash
export TMPDIR="/mnt/scratchpad/pytest_tmp"
export TF_PLUGIN_CACHE_DIR="/mnt/scratchpad/terraform/plugin_cache"
export TF_DATA_DIR="/mnt/scratchpad/terraform/.terraform"
pytest -o cache_dir=/mnt/scratchpad/pytest_tmp/.pytest_cache
```

## Locked this afternoon

- `EFS_MOUNT_TARGET_PUBLIC_ACCESSIBLE` — 167s
- `EBS_OPTIMIZED_INSTANCE` — 210s; `HARNESS_EBS_OPT_TYPE=c3.xlarge` NC + t3.nano C
  - nc `i-01cf1611d88f4aad6` / c `i-0ca362133716d13a3`
  - both terminated; SG `sg-073136aa8591ca1a1` deleted
  - m4/c4/t3 are default-on and cannot prove NC in this region

## Locked this morning (6)

- `EC2_LAUNCH_TEMPLATES_EBS_VOLUME_ENCRYPTED`
- `EFS_FILESYSTEM_CT_ENCRYPTED`
- `EC2_EBS_ENCRYPTION_BY_DEFAULT`
- `CLOUDTRAIL_ALL_WRITE_S3_DATA_EVENT_CHECK`
- `CLOUDTRAIL_ALL_READ_S3_DATA_EVENT_CHECK`
- `S3_ACCOUNT_LEVEL_PUBLIC_ACCESS_BLOCKS_PERIODIC`

## Parked

RP encrypted; EBS protected-by-plan; snapshot BPA stale CI;
RCP; SSE-S3; FSx OpenZFS; snapshot C path.

## Next

Do not apply Terraform. Remaining rows are long-shots (MFA delete, S3 Express,
air-gapped vault, restore-time, last-RP-created, spot-fleet CT, other FSx,
coverage-family backup rules).
