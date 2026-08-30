# Resume note — aws-test-harness

Last updated: 2026-08-30 06:10 EDT

## Score

Storage CP live **38 / 59**. Partial 1. Parked 10. Catalog-only 10.
Do not apply Terraform drift. Do not widen EC2-SSM-Role.

## Recorder inventory (SSM, 2026-08-30 10:09 UTC)

Recorder `default` recording=True lastStatus=SUCCESS.
70 discovered types. Present: BackupPlan=1, BackupSelection=1, BackupVault=5.
Absent (list n=0): RecoveryPoint, LogicallyAirGappedBackupVault,
RestoreTestingPlan, EC2 SpotFleet, FSx FileSystem, S3Express DirectoryBucket.

GHA under EC2-SSM-Role cannot call Config inventory APIs. Live cycles stay on SSM.

## Closed this morning

- S3 Express — control-plane endpoint unreachable from private subnet
- Spot Fleet — no fleet IAM role; type not in recorder
- RecoveryPoint family — Config count stays 0 after completed Backup jobs
- FSx family — FileSystem never discovered
- Air-gapped vault / restore-time — types not in recorder; do not create them here

## Locked 2026-08-29 evening

- `S3_LAST_BACKUP_RECOVERY_POINT_CREATED` on `cfg-test-ef57dcf4-ca589695`
