# Resume note — aws-test-harness

Last updated: 2026-08-27 16:17 EDT

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited.

**EBS** — `ENCRYPTED_VOLUMES`. Snapshot public-restorable partial only.

**EFS** — encrypted, automatic backups, access points.

**CloudTrail** — log-file validation this host. KMS encryption on the other machine.

**EC2** — IMDSv2, restricted SSH. Proven.

**Backup** — `test_backup_rules.py` min frequency/retention. PASSED 16:17 EDT.

## Gaps

**restricted-common-ports / RESTRICTED_INCOMING_TRAFFIC** — implemented; live eval returned empty results for 600s. Parked.

**S3 encryption** — default AES256; skip.

**CloudTrail KMS** — skip on this host (ARN on the other machine).

**FSx** — deferred (cost / time).

## Next

FSx only if you want it. Otherwise destroy Terraform and stop the recorder.
