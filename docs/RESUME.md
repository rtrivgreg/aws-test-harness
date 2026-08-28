# Resume note — aws-test-harness

Last updated: 2026-08-28 08:59 EDT

## Score

Grade this iteration: **A** (CloudTrail KMS locked first try on this box).
Portfolio live proofs: **22 / 26 = 85%**.
Session grade: **A-**.

CLOUDTRAIL_KMS_KEY_ARN = alias/harness
`arn:aws:kms:us-east-1:418295699841:key/45b99a45-cb78-47e5-9f70-0296ef21bee7`

## Locked live proofs (22)

**S3 (10)** versioning, lifecycle, version-lifecycle, public-access,
SSL, logging, public-read, public-write, ACL prohibited,
S3_DEFAULT_ENCRYPTION_KMS.

**EBS (1)** ENCRYPTED_VOLUMES.

**EFS (3)** encrypted, backups, access points.

**CloudTrail (2)** log-file validation, CLOUD_TRAIL_ENCRYPTION_ENABLED
(run ef57dcf4, alias/harness).

**EC2 (3)** IMDSv2, restricted SSH, vpc-sg-port-restriction-check.

**Backup (1)** min frequency/retention.

## Parked (not in 85%)

RESTRICTED_INCOMING_TRAFFIC (INSUFFICIENT_DATA).
S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED (platform default SSE).
FSx OpenZFS (AVAILABLE, Config never discovered; destroyed).
EBS snapshot public-restorable (NC proven; C account-scoped xfail).
