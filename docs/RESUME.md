# Resume note — aws-test-harness

Last updated: 2026-08-30 05:25 EDT

## Score

Storage CP live **38 / 59**. Partial 1. Parked 9. Catalog-only 11.
Do not apply Terraform drift.

## This morning

Self-hosted runner Idle on `ip-10-0-1-190` (`/mnt/scratchpad/actions-runner`).
Dispatch workflow `.github/workflows/harness-ec2.yml` works (runs 1–2).

Parked `S3EXPRESS_DIR_BUCKET_LIFECYCLE_RULES_CHECK`:
botocore CreateSession always hits
`https://<bucket>.s3express-control.us-east-1.amazonaws.com/?session`
(EndpointConnectionError on use1-az4/5/6). Path-style config does not stop it.
This VPC has no working s3express-control path. Do not rerun until an
`s3express` interface endpoint exists. Do not leave directory buckets around;
none were created.

## Locked 2026-08-29 evening

- `S3_LAST_BACKUP_RECOVERY_POINT_CREATED` on `cfg-test-ef57dcf4-ca589695`

## Parked — do not rerun on this recorder / this VPC

EBS_IN_BACKUP_PLAN; EBS_LAST_BACKUP_RECOVERY_POINT_CREATED;
RP encrypted; EBS protected-by-plan; snapshot BPA; snapshot C path;
SSE-S3; FSx OpenZFS; RCP; S3 Express directory-bucket lifecycle.
