# Resume note — aws-test-harness

Last updated: 2026-08-28 07:41 EDT

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited,
SSL, logging, public-read, public-write, ACL prohibited.

**EBS** — ENCRYPTED_VOLUMES. Snapshot public-restorable partial.

**EFS** — encrypted, backups, access points.

**CloudTrail** — log-file validation (KMS on other machine).

**EC2** — IMDSv2, restricted SSH, vpc-sg-port-restriction-check
(3389 open/close on sg-07fa913d0e8961833, run ef57dcf4).

**Backup** — min frequency/retention.

## Next

S3 default encryption (`s3_toggle.make_encryption_*` already exists).

`pytest tests/test_s3_rules.py -k encryption -v -s`
or add a dedicated test if that selector is empty.

## Parked

**RESTRICTED_INCOMING_TRAFFIC / restricted-common-ports** — INSUFFICIENT_DATA
+ empty EvaluationResults after successful invocation. Skipped in pytest.

FSx (not discovered).
