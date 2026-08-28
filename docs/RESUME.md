# Resume note — aws-test-harness

Last updated: 2026-08-28 17:45 EDT

## Score

Portfolio live proofs: **25** (was 22 at 10:05 freeze).
Storage CP live rows: treat events + replication as live; matrix on disk may still lag.
Session grade tonight: **A** for two clean S3 cycles on EC2.
Do not apply Terraform drift. Next pytest only for a chosen catalog-only S3 rule on the same buckets.

## Locked live proofs (25)

**S3 (13)** versioning, lifecycle, version-lifecycle, public-access,
SSL, logging, public-read, public-write, ACL prohibited,
S3_DEFAULT_ENCRYPTION_KMS, S3_BUCKET_TAGGED (HarnessProof),
S3_EVENT_NOTIFICATIONS_ENABLED (SQS destination),
S3_BUCKET_REPLICATION_ENABLED (test → logs bucket).
Bucket pair: `cfg-test-ef57dcf4-ca589695` /
`cfg-test-logs-ef57dcf4-ca589695`.

Tonight on `ip-10-0-1-190` (linux, run `ef57dcf4`):

- `tests/test_s3_events_rules.py::test_s3_event_notifications_enabled` PASSED
- `tests/test_s3_replication_rules.py::test_s3_bucket_replication_enabled` PASSED

**EBS (1)** ENCRYPTED_VOLUMES.

**EFS (3)** encrypted, backups, access points.

**CloudTrail (2)** log-file validation, CLOUD_TRAIL_ENCRYPTION_ENABLED
(`cfg-ct-ef57dcf4`, `alias/harness`
`arn:aws:kms:us-east-1:418295699841:key/45b99a45-cb78-47e5-9f70-0296ef21bee7`).
Trail is **not** in Terraform state. Do not enable the module to “fix” that.

**EC2 (3)** IMDSv2, restricted SSH, vpc-sg-port-restriction-check
(`sg-07fa913d0e8961833`).

**Backup (1)** min frequency/retention.

## Parked (unchanged)

- RESTRICTED_INCOMING_TRAFFIC — invokes; INSUFFICIENT_DATA + empty evals.
- S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED — modern S3 always SSE-S3.
- FSx OpenZFS — fs AVAILABLE; Config inventory empty; destroyed.
- EBS snapshot public-restorable — NC proven; C is account-scoped xfail.

## Terraform backend (2026-08-28)

Remote state owns **only** `module.s3_test_bucket[0].…` (nine addresses).

- Bucket: `tfstate-aws-test-harness-418295699841`
- Key: `aws-test-harness/terraform.tfstate`
- Lock table: `tfstate-aws-test-harness-lock` (`860c7062-08b5-4029-8737-00e3cb12f213`)
- Region: `us-east-1`
- Runner: Ubuntu EC2 `ip-10-0-1-190` only. Mac does not run Terraform or live pytest.

`terraform plan` (defaults, no `TF_VAR_enable_*`): 0 add, 0 destroy,
2 in-place on the test bucket (strip harness toggle tags; versioning
Enabled → Suspended). That is pytest residue. **Do not apply.**
Replication left versioning Enabled; a later apply would suspend it.

## Next session on EC2

```bash
cd ~/repost/aws-test-harness
git pull
source .venv/bin/activate
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
export CATALOG_TABLE_NAME=y62db-config-rule-catalog
export CATALOG_GROUP=default
export TEST_RUN_ID=ef57dcf4
export TF_VAR_test_run_id=ef57dcf4
export TF_VAR_aws_region=us-east-1
export CLOUDTRAIL_KMS_KEY_ARN=arn:aws:kms:us-east-1:418295699841:key/45b99a45-cb78-47e5-9f70-0296ef21bee7

aws sts get-caller-identity
aws configservice describe-configuration-recorder-status --region us-east-1
cd terraform && terraform plan -input=false && cd ..
```

Do not export `TF_VAR_enable_*`. Do not enable FSx. Do not rerun
restricted-common-ports. Pytest from repo root, one live S3 rule at a time.
