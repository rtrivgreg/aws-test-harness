# Resume note — aws-test-harness

Last updated: 2026-08-29 13:30 EDT

## Score

Storage CP live **33 / 59**. Partial 1. Parked 6. Catalog-only 19.
Do not apply Terraform drift.

## Runner disk (t3.medium)

Root is tight. 20G extra volume is mounted at `/mnt/scratchpad` (`nvme1n1`).

```bash
export TMPDIR="/mnt/scratchpad/pytest_tmp"
export TF_PLUGIN_CACHE_DIR="/mnt/scratchpad/terraform/plugin_cache"
export TF_DATA_DIR="/mnt/scratchpad/terraform/.terraform"
pytest -o cache_dir=/mnt/scratchpad/pytest_tmp/.pytest_cache
```

`--cache-dir` is not a pytest 9.1.1 flag. Use `-o cache_dir=...`.

## Locked this afternoon

- `EFS_MOUNT_TARGET_PUBLIC_ACCESSIBLE` — 167s; public-subnet MT NC / private-subnet MT C
  - nc FS `fs-0e4463735c99d6330` mt `fsmt-0899847926d77d7d5`
  - c FS `fs-06e028de078bdd97f` mt `fsmt-0c4d16d42e21cf831`
  - throwaway SG + private /28 deleted in cleanup
  - first miss: default VPC `vpc-0c4f804e905f41635` had no private subnet; harness now uses instance VPC via IMDS

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

Do not apply Terraform. Least-bad remaining: `EBS_OPTIMIZED_INSTANCE`.
