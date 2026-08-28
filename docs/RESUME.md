# Resume note — aws-test-harness

Last updated: 2026-08-28 10:05 EDT

## Score (frozen this session)

Portfolio live proofs: **22 / 26 = 85%**.
Session grade: **A-**.
No further pytest unless a new family is chosen on purpose.

## Locked live proofs (22)

**S3 (10)** versioning, lifecycle, version-lifecycle, public-access,
SSL, logging, public-read, public-write, ACL prohibited,
S3_DEFAULT_ENCRYPTION_KMS (`cfg-test-ef57dcf4-ca589695`).

**EBS (1)** ENCRYPTED_VOLUMES.

**EFS (3)** encrypted, backups, access points.

**CloudTrail (2)** log-file validation, CLOUD_TRAIL_ENCRYPTION_ENABLED
(`cfg-ct-ef57dcf4`, `alias/harness`
`arn:aws:kms:us-east-1:418295699841:key/45b99a45-cb78-47e5-9f70-0296ef21bee7`).

**EC2 (3)** IMDSv2, restricted SSH, vpc-sg-port-restriction-check
(`sg-07fa913d0e8961833`).

**Backup (1)** min frequency/retention.

## Parked (not in 85%)

- RESTRICTED_INCOMING_TRAFFIC — invokes; INSUFFICIENT_DATA + empty evals.
- S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED — modern S3 always SSE-S3.
- FSx OpenZFS — fs AVAILABLE; Config inventory empty; destroyed.
- EBS snapshot public-restorable — NC proven; C is account-scoped xfail.

## Terraform backend (2026-08-28)

Migrated local state → S3. Same state, same `ef57dcf4` resources.

- Bucket: `tfstate-aws-test-harness-418295699841`
- Key: `aws-test-harness/terraform.tfstate`
- Lock table: `tfstate-aws-test-harness-lock` (`860c7062-08b5-4029-8737-00e3cb12f213`)
- Region: `us-east-1`
- Runner: this EC2 only. Mac does not run Terraform.

Plan without `TF_VAR_enable_cloudtrail_test=true` wants to destroy the trail
(module count 0). That is not drift. Do not apply it.

Plan with the flag shows 1 in-place change (strip KMS + harness tags).
That is pytest toggle drift. Do not apply it.

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
export CLOUDTRAIL_KMS_KEY_ARN=arn:aws:kms:us-east-1:418295699841:key/45b99a45-cb78-47e5-9f70-0296ef21bee7
```

Do not enable FSx. Do not rerun restricted-common-ports.
