# Resume note — aws-test-harness

Last updated: 2026-08-29 05:40 EDT

## Score

Portfolio live proofs: **32** standing.
Storage CP matrix live **26** / 59 pending this morning's RP cycle.
Do not apply Terraform drift.

## Backend (confirmed 2026-08-29)

- `tfstate-aws-test-harness-418295699841` versioning **Enabled**.
- Lock table `tfstate-aws-test-harness-lock` **ACTIVE**.
- Recorder on. Env vars set. venv active.
- Live test bucket `cfg-test-ef57dcf4-ca589695` versioning **Suspended**
  (leftover from S3_BUCKET_VERSIONING_ENABLED toggle). Leave it.
- Extra buckets from older run still present: `cfg-test-14ac09fc-68e6193a`
  and `cfg-test-logs-14ac09fc-68e6193a`. Do not delete mid-session.

## Locked (EC2, run ef57dcf4)

Events, replication, grantee, blacklisted-actions, AP PAB, AP VPC-only,
policy-not-more-permissive, cross-region replication, default object lock,
plus prior S3/EBS/EFS/CT/EC2/Backup-plan locks.

Bucket pair: `cfg-test-ef57dcf4-ca589695` / `cfg-test-logs-ef57dcf4-ca589695`.

## This session — lane A

`BACKUP_RECOVERY_POINT_ENCRYPTED` via throwaway EBS volumes + vault.
No Terraform apply. EBS RP encryption follows the source volume.

```bash
cd ~/repost/aws-test-harness
git pull
source .venv/bin/activate
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
export CATALOG_TABLE_NAME=y62db-config-rule-catalog CATALOG_GROUP=default
export TEST_RUN_ID=ef57dcf4
export S3_TEST_BUCKET=cfg-test-ef57dcf4-ca589695
pytest -q tests/test_backup_recovery_point_rules.py --tb=short
```

Needs IAM role `AWSBackupDefaultServiceRole`.

## Parked

RESTRICTED_INCOMING_TRAFFIC; S3 SSE-S3 implicit; FSx destroyed;
EBS snapshot public-restorable C path.

## Terraform

State owns only `module.s3_test_bucket[0].…`. EC2 only. Do not apply.
