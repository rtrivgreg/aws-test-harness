# Resume note — aws-test-harness

Last updated: 2026-08-29 14:33 EDT

## Score

Storage CP live **35 / 59**. Partial 1. Parked 6. Catalog-only 17.
Do not apply Terraform drift.

## Runner disk

```bash
export TMPDIR=/mnt/scratchpad/pytest_tmp
export TF_PLUGIN_CACHE_DIR=/mnt/scratchpad/terraform/plugin_cache
export TF_DATA_DIR=/mnt/scratchpad/terraform/.terraform
pytest -o cache_dir=/mnt/scratchpad/pytest_tmp/.pytest_cache
```

## Locked this afternoon

- `EFS_MOUNT_TARGET_PUBLIC_ACCESSIBLE` — 167s
- `EBS_OPTIMIZED_INSTANCE` — 210s; c3.xlarge NC + t3.nano C
- `EFS_IN_BACKUP_PLAN` — 256s; off-plan NC / on-plan C; boto3 only
  - fs `fs-0c6be07b1650babdb` plan `45e12992-8ac4-40c5-bf90-babce9c25026`
  - first miss: `resourceId` is not a valid inputParameter on this identifier

## Parked

RP encrypted; EBS protected-by-plan; snapshot BPA stale CI;
RCP; SSE-S3; FSx OpenZFS; snapshot C path.

## Next

Do not apply Terraform. `EFS_RESOURCES_PROTECTED_BY_BACKUP_PLAN` is the twin;
EBS version of that identifier parked INSUFFICIENT_DATA. Optional next or stop.
