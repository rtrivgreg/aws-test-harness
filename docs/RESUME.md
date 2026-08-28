# Resume note — aws-test-harness

Last updated: 2026-08-28 18:50 EDT

## Score

Portfolio live proofs: **27**.
S3 family **15**. Do not apply Terraform drift.

## Locked live proofs (27)

**S3 (15)** versioning, lifecycle, version-lifecycle, public-access,
SSL, logging, public-read, public-write, ACL prohibited,
S3_DEFAULT_ENCRYPTION_KMS, S3_BUCKET_TAGGED,
S3_EVENT_NOTIFICATIONS_ENABLED, S3_BUCKET_REPLICATION_ENABLED,
S3_BUCKET_POLICY_GRANTEE_CHECK,
S3_BUCKET_BLACKLISTED_ACTIONS_PROHIBITED (`blacklistedActionPattern`).
Bucket pair: `cfg-test-ef57dcf4-ca589695` /
`cfg-test-logs-ef57dcf4-ca589695`.

Tonight on `ip-10-0-1-190` (linux, run `ef57dcf4`):

- events PASSED
- replication PASSED
- policy-grantee PASSED
- blacklisted-actions PASSED

**EBS (1)** ENCRYPTED_VOLUMES.

**EFS (3)** encrypted, backups, access points.

**CloudTrail (2)** log-file validation, CLOUD_TRAIL_ENCRYPTION_ENABLED
(`cfg-ct-ef57dcf4`, `alias/harness`).
Trail is **not** in Terraform state.

**EC2 (3)** IMDSv2, restricted SSH, vpc-sg-port-restriction-check.

**Backup (1)** min frequency/retention.

## Parked (unchanged)

- RESTRICTED_INCOMING_TRAFFIC
- S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED
- FSx OpenZFS (destroyed)
- EBS snapshot public-restorable COMPLIANT path

## Terraform backend

State owns only `module.s3_test_bucket[0].…`. Runner: EC2 only.
Plan in-place S3 drift: **do not apply.**

## Next session on EC2

```bash
cd ~/repost/aws-test-harness
git pull
source .venv/bin/activate
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
export CATALOG_TABLE_NAME=y62db-config-rule-catalog CATALOG_GROUP=default
export TEST_RUN_ID=ef57dcf4
export TF_VAR_test_run_id=ef57dcf4 TF_VAR_aws_region=us-east-1
```

Pytest from repo root, one S3 rule at a time. No `TF_VAR_enable_*`.
