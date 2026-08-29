# Resume note — aws-test-harness

Last updated: 2026-08-29 14:42 EDT

## Score

Storage CP live **36 / 59**. Partial 1. Parked 6. Catalog-only 16.
Do not apply Terraform drift.

## Runner disk

```bash
export TMPDIR=/mnt/scratchpad/pytest_tmp
export TF_PLUGIN_CACHE_DIR=/mnt/scratchpad/terraform/plugin_cache
export TF_DATA_DIR=/mnt/scratchpad/terraform/.terraform
pytest -o cache_dir=/mnt/scratchpad/pytest_tmp/.pytest_cache
```

## Locked this afternoon (boto3, no Terraform apply)

- `EFS_MOUNT_TARGET_PUBLIC_ACCESSIBLE` — 167s
- `EBS_OPTIMIZED_INSTANCE` — 210s; c3.xlarge NC + t3.nano C
- `EFS_IN_BACKUP_PLAN` — 256s
- `EFS_RESOURCES_PROTECTED_BY_BACKUP_PLAN` — 241s; resourceId accepted
  - fs `fs-05c790fc2da4c6f25` plan `a4e45987-544e-438a-b527-88083abd5990`
  - EBS twin of this identifier remains parked INSUFFICIENT_DATA

## Parked

RP encrypted; EBS protected-by-plan; snapshot BPA stale CI;
RCP; SSE-S3; FSx OpenZFS; snapshot C path.

## EFS in the 59

Live: encrypted, CT encrypted, automatic backups, both AP rules,
mount-target public, in-backup-plan, protected-by-plan.
No remaining EFS row in this pack except coverage that is already done.

## Next

Do not apply Terraform. Remaining catalog-only are long-shots
(MFA delete, S3 Express, air-gapped vault, restore-time, last-RP,
spot-fleet CT, other FSx, EBS-in-backup-plan).
