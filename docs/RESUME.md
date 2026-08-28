# Resume note — aws-test-harness

Last updated: 2026-08-28 08:00 EDT

## Score

Grade this iteration: **A** (KMS encryption locked first try).
Portfolio live proofs: **21 / 26 = 81%**.
Session grade: **A-**.

## Locked live proofs (21)

**S3 (10)** versioning, lifecycle, version-lifecycle, public-access,
SSL, logging, public-read, public-write, ACL prohibited,
S3_DEFAULT_ENCRYPTION_KMS (AES256 NC / aws:kms C on
cfg-test-ef57dcf4-ca589695).

**EBS (1)** ENCRYPTED_VOLUMES.

**EFS (3)** encrypted, backups, access points.

**CloudTrail (1)** log-file validation.

**EC2 (3)** IMDSv2, restricted SSH, vpc-sg-port-restriction-check.

**Backup (1)** min frequency/retention.

## Next iteration

FSx OpenZFS copy-tags. Needs TF_VAR_enable_fsx_test, OpenZFS billable,
Config discovery wait up to 20 min.

```bash
git pull
pytest tests/test_fsx_rules.py -v -s
```

## Parked

RESTRICTED_INCOMING_TRAFFIC (INSUFFICIENT_DATA).
S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED (platform default SSE).
EBS snapshot public-restorable (NC proven; C is account-scoped xfail).
CloudTrail KMS (other machine).
