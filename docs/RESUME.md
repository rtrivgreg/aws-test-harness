# Resume note — aws-test-harness

Last updated: 2026-08-30 05:42 EDT

## Score

Storage CP live **38 / 59**. Partial 1. Parked 10. Catalog-only 10.
Do not apply Terraform drift.

## This morning

Self-hosted runner works. Instance profile `EC2-SSM-Role` on `i-015cc0059621c1a1c`.

Parked `S3EXPRESS_DIR_BUCKET_LIFECYCLE_RULES_CHECK` — s3express-control unreachable.

Parked `EC2_SPOT_FLEET_REQUEST_CT_ENCRYPTION_AT_REST` — no Spot Fleet IAM role
and `EC2-SSM-Role` cannot `iam:CreateRole` / no matching GetRole.
Unpark if you create `aws-ec2-spot-fleet-tagging-role` with
`AmazonEC2SpotFleetTaggingRole` (or set `HARNESS_SPOT_FLEET_ROLE_ARN`) and
`iam:PassRole` for that role on the instance profile.

## Locked 2026-08-29 evening

- `S3_LAST_BACKUP_RECOVERY_POINT_CREATED` on `cfg-test-ef57dcf4-ca589695`
