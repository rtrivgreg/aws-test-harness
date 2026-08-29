# Safeguards (2026-08-28)

Cause of the CloudTrail loss: pytest `terraform apply -auto-approve` with
default module flags while non-S3 modules were still in state.

## In force

1. `S3_TEST_BUCKET` set → pytest does **not** call Terraform.
2. Any pytest Terraform path requires `HARNESS_ALLOW_TF_APPLY=1` and refuses a plan that contains `delete`.
3. `lifecycle.prevent_destroy = true` on S3 buckets, CloudTrail trail+log bucket, EBS volumes/instance/SG, EFS FS/APs, EC2 instance/SG, Backup vault/plan.
4. `terraform/live.auto.tfvars` matches current state (S3 only).
5. `scripts/tf-safe.sh plan|apply` — apply also needs `HARNESS_ALLOW_TF_APPLY=1`.

## Before every apply

```bash
cd ~/repost/aws-test-harness
./scripts/tf-safe.sh plan
terraform -chdir=terraform state list
```

State list must stay S3-only unless you are **creating** a family on purpose.
