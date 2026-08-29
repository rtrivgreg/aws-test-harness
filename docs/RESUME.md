# Resume note — aws-test-harness

Last updated: 2026-08-29 07:12 EDT

## Score

Portfolio live proofs: **32** standing.
Storage CP matrix live **26** / 59. Parked **4**.
Do not apply Terraform drift. Do not StartConfigRulesEvaluation-spam.

## Backend

- tfstate versioning Enabled; lock table ACTIVE.
- Live bucket `cfg-test-ef57dcf4-ca589695` versioning Suspended (toggle leftover).
- Older `14ac09fc` bucket pair still listed.

## Locked

S3 family as of 2026-08-28 plus EBS encrypted volumes, EFS, CloudTrail,
EC2 IMDSv2/SSH/port-restriction, Backup plan min frequency/retention.

## Parked 2026-08-29 morning

- `BACKUP_RECOVERY_POINT_ENCRYPTED` — jobs COMPLETED; Config RecoveryPoint inventory [].
- `EBS_RESOURCES_PROTECTED_BY_BACKUP_PLAN` — volume `vol-095b48e3080b93ae0`
  discovered; eval finished in ~5s; ComplianceType **INSUFFICIENT_DATA**;
  EvaluationResults **[]**. Same engine miss as RESTRICTED_INCOMING_TRAFFIC.
  Config *does* record BackupPlan/Selection/Vault, but only
  `aws/efs/automatic-backup-*`. Do not rerun. Do not rerun EFS/S3
  `*_IN_BACKUP_PLAN` / `*_PROTECTED_BY_BACKUP_PLAN` on this recorder.

Also parked from earlier: RCP; implicit SSE-S3; FSx OpenZFS; snapshot C path.

## Cleanup still owed

```bash
aws configservice delete-config-rule \
  --config-rule-name harness-ebs-resources-protected-by-backup-plan-ef57dcf4
aws ec2 delete-volume --volume-id vol-095b48e3080b93ae0 --region us-east-1
```

Leave `cfg-rp-vault-ef57dcf4` if DeleteBackupVault stays denied.

## Next session

Change-triggered rules whose type already has CIs and a working toggle.
Not Backup coverage, not RecoveryPoint.

```bash
cd ~/repost/aws-test-harness && git pull && source .venv/bin/activate
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
export CATALOG_TABLE_NAME=y62db-config-rule-catalog CATALOG_GROUP=default
export TEST_RUN_ID=ef57dcf4
export S3_TEST_BUCKET=cfg-test-ef57dcf4-ca589695
```

## Terraform

State owns only `module.s3_test_bucket[0].…`. EC2 only. Do not apply.
