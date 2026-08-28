# Resume note — aws-test-harness

Last updated: 2026-08-28 07:43 EDT

## Score

Grade this session: **B+** (ACL + ports replacement locked; RCP burned ~90 min).
Portfolio live proofs: **20 / 26 = 77%**.

## Locked live proofs (20)

**S3 (9)** versioning, lifecycle, version-lifecycle, public-access,
SSL, logging, public-read, public-write, ACL prohibited.

**EBS (1)** ENCRYPTED_VOLUMES. Snapshot public-restorable = partial, not counted.

**EFS (3)** encrypted, backups, access points.

**CloudTrail (1)** log-file validation.

**EC2 (3)** IMDSv2, restricted SSH, vpc-sg-port-restriction-check.

**Backup (1)** min frequency/retention.

## This iteration (in progress)

**S3_DEFAULT_ENCRYPTION_KMS** — AES256 = NC, aws:kms = C.
`S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED` stays parked: modern S3 is
always SSE-S3; NC cannot be proven by delete_bucket_encryption.

```bash
git pull
pytest tests/test_s3_kms_encryption_rules.py -v -s
```

## Parked (not in the 77% numerator)

RESTRICTED_INCOMING_TRAFFIC (INSUFFICIENT_DATA).
S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED (platform default SSE).
FSx (not discovered).
EBS snapshot public-restorable (partial).
CloudTrail KMS (other machine).
