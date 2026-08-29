# Resume note — aws-test-harness

Last updated: 2026-08-29 13:00 EDT

## Score

Storage CP live **32 / 59**. Partial 1. Parked 6. Catalog-only 20.
Do not apply Terraform drift.

## Runner disk (t3.medium)

Root is tight. 20G extra volume is mounted at `/mnt/scratchpad` (`nvme1n1`).
Terraform plugin cache, TF data dir, and pytest tmp live there:

```bash
# already created on ip-10-0-1-190
# /mnt/scratchpad/terraform/plugin_cache
# /mnt/scratchpad/terraform/tmp
# /mnt/scratchpad/pytest_tmp/.pytest_cache

export TMPDIR="/mnt/scratchpad/pytest_tmp"
export TF_PLUGIN_CACHE_DIR="/mnt/scratchpad/terraform/plugin_cache"
export TF_DATA_DIR="/mnt/scratchpad/terraform/.terraform"
# also in ~/.bashrc

pytest --cache-dir=/mnt/scratchpad/pytest_tmp/.pytest_cache
```

Do not run Terraform or pytest against `/tmp` on the root volume.

## Locked this morning (6)

- `EC2_LAUNCH_TEMPLATES_EBS_VOLUME_ENCRYPTED`
- `EFS_FILESYSTEM_CT_ENCRYPTED`
- `EC2_EBS_ENCRYPTION_BY_DEFAULT`
- `CLOUDTRAIL_ALL_WRITE_S3_DATA_EVENT_CHECK`
- `CLOUDTRAIL_ALL_READ_S3_DATA_EVENT_CHECK`
- `S3_ACCOUNT_LEVEL_PUBLIC_ACCESS_BLOCKS_PERIODIC` — 147s; account PAB all-true restored

## Parked

RP encrypted; EBS protected-by-plan; snapshot BPA stale CI;
RCP; SSE-S3; FSx OpenZFS; snapshot C path.

## Break / next

Account PAB confirmed all four true. Encryption-by-default left enabled.
Do not apply Terraform. Remaining rows are long-shots (MFA delete, S3 Express,
air-gapped vault, restore-time, spot fleet CT, FSx other engines, Backup RP
types this recorder will not discover).
