# Resume note — aws-test-harness

Last updated: 2026-08-28 19:52 EDT

## Score

Portfolio live proofs: **32**.
S3 family **20**. Storage CP matrix live **26** / 59.
Do not apply Terraform drift.

## Locked tonight (EC2, run ef57dcf4)

Events, replication, grantee, blacklisted-actions, AP PAB, AP VPC-only,
policy-not-more-permissive, cross-region replication, default object lock.

Bucket pair: `cfg-test-ef57dcf4-ca589695` / `cfg-test-logs-ef57dcf4-ca589695`.
Lock bucket `cfg-test-lock-ca589695` should be deleted.

## Parked

RESTRICTED_INCOMING_TRAFFIC; S3 SSE-S3 implicit; FSx destroyed;
EBS snapshot public-restorable C path.

## Terraform

State owns only `module.s3_test_bucket[0].…`. EC2 only. Do not apply.

## Next session

```bash
cd ~/repost/aws-test-harness
git pull
source .venv/bin/activate
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
export CATALOG_TABLE_NAME=y62db-config-rule-catalog CATALOG_GROUP=default
export TEST_RUN_ID=ef57dcf4
export TF_VAR_test_run_id=ef57dcf4 TF_VAR_aws_region=us-east-1
```
