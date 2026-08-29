# Resume note — aws-test-harness

Last updated: 2026-08-29 06:12 EDT

## Score

Portfolio live proofs: **32** standing.
Storage CP matrix live **26** / 59. Parked **3**.
Do not apply Terraform drift.

## Backend (confirmed 2026-08-29)

- `tfstate-aws-test-harness-418295699841` versioning **Enabled**.
- Lock table `tfstate-aws-test-harness-lock` **ACTIVE**.
- Recorder on.
- Live test bucket `cfg-test-ef57dcf4-ca589695` versioning **Suspended** (toggle leftover).
- Older run buckets still present: `cfg-test-14ac09fc-68e6193a` / logs twin.

## Locked (EC2, run ef57dcf4)

S3 family as of 2026-08-28 plus EBS encrypted volumes, EFS, CloudTrail,
EC2 IMDSv2/SSH/port-restriction, Backup plan min frequency/retention.

Bucket pair: `cfg-test-ef57dcf4-ca589695` / `cfg-test-logs-ef57dcf4-ca589695`.

## Parked 2026-08-29 — BACKUP_RECOVERY_POINT_ENCRYPTED

Two EBS on-demand jobs COMPLETED. RP ARNs are EC2 snapshot ARNs.
`list-discovered-resources --resource-type AWS::Backup::RecoveryPoint` = [].
Do not rerun. Sibling RP rules (manual-deletion, min-retention) stay catalog-only
until this recorder inventories that type.

Leftover job snapshots (delete if still present):

- `arn:aws:ec2:us-east-1::snapshot/snap-0ed309ee3a0da0752`
- `arn:aws:ec2:us-east-1::snapshot/snap-023c1211f37c3fb71`
- volumes `vol-0d2fc1f68ad84617f` `vol-083f9e5a4a3c260ba`
- vault `cfg-rp-vault-ef57dcf4` (DescribeBackupVault is AccessDenied on this role)

## Other parked

RESTRICTED_INCOMING_TRAFFIC; S3 SSE-S3 implicit; FSx OpenZFS;
EBS snapshot public-restorable C path.

## Next

Lane B: `EBS_RESOURCES_PROTECTED_BY_BACKUP_PLAN` or `EFS_IN_BACKUP_PLAN`
(resource types Config already records). No terraform apply.

```bash
cd ~/repost/aws-test-harness
git pull
source .venv/bin/activate
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
export CATALOG_TABLE_NAME=y62db-config-rule-catalog CATALOG_GROUP=default
export TEST_RUN_ID=ef57dcf4
export S3_TEST_BUCKET=cfg-test-ef57dcf4-ca589695
```

## Terraform

State owns only `module.s3_test_bucket[0].…`. EC2 only. Do not apply.
