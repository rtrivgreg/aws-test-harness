# AWS Config Rule Test Harness

Framework for validating AWS Config **managed rules** with a Terraform-provisioned
resource toggled between COMPLIANT and NON_COMPLIANT.

**Live proofs (2026-08-28): 22 / 26 = 85%.** Details in `docs/RESUME.md`.

## Design principles

- **Terraform** owns durable test resources and state.
- **pytest** owns rule lifecycle and assertions.
- **DynamoDB catalog** (`y62db-config-rule-catalog`) is the system of record
  for rule parameters / group bindings (same table as `cpgNG.py`).
- Every resource and Config rule carries a `test-run-id` tag.
- Dry-run is supported. Never delete untagged resources.

## Locked vs parked

Locked: S3 (10, including KMS default encryption and ACL prohibited),
EBS encrypted volumes, EFS (encrypted / backups / access points),
CloudTrail (log-file validation + KMS), EC2 (IMDSv2, restricted SSH,
vpc-sg-port-restriction-check), Backup min frequency/retention.

Parked on purpose (do not rerun):

- `RESTRICTED_INCOMING_TRAFFIC` — INSUFFICIENT_DATA, empty EvaluationResults
- `S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED` — SSE-S3 is implicit on modern buckets
- FSx OpenZFS — filesystem AVAILABLE; Config never discovered it
- EBS snapshot public-restorable COMPLIANT — account-scoped periodic rule

## Terraform state

Remote backend (migrated 2026-08-28 from local state on the harness EC2):

```hcl
backend "s3" {
  bucket         = "tfstate-aws-test-harness-418295699841"
  key            = "aws-test-harness/terraform.tfstate"
  region         = "us-east-1"
  dynamodb_table = "tfstate-aws-test-harness-lock"
  encrypt        = true
}
```

- Terraform runs **only on the Ubuntu EC2** (`ip-10-0-1-190`). Not on the Mac.
- Current live run id: `ef57dcf4`.
- CloudTrail module is gated by `TF_VAR_enable_cloudtrail_test=true`.
  A plan without that flag will propose destroying the trail; that is expected.
- Do not apply toggle drift (KMS key / harness tags on the trail).

## Daily resume (EC2)

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

aws configservice describe-configuration-recorder-status --region us-east-1
```

Run pytest from the **repo root**, not from `terraform/`.

## High-level flow (per managed rule)

1. Terraform provisions or reuses a tagged test resource.
2. `PutConfigRule` with catalog parameters.
3. Toggle NON_COMPLIANT → evaluate → assert.
4. Toggle COMPLIANT → evaluate → assert.
5. Delete the harness Config rule. Leave or destroy the Terraform resource.

## Safety

- Dedicated test account preferred.
- Start with `--dry-run` for a new family.
- Config recorder in this account uses `EXCLUSION_BY_RESOURCE_TYPES` (IAM only excluded).
