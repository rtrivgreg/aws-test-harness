# Resume note — aws-test-harness

Last updated: 2026-08-28 07:22 EDT

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited,
SSL, logging, public-read, public-write, ACL prohibited.

**EBS** — ENCRYPTED_VOLUMES. Snapshot public-restorable partial.

**EFS** — encrypted, backups, access points.

**CloudTrail** — log-file validation (KMS on other machine).

**EC2** — IMDSv2, restricted SSH.

**Backup** — min frequency/retention.

## In flight

**vpc-sg-port-restriction-check** — replacement for restricted-common-ports.
Same SG, same 3389 open/close toggle.

Re-run: `git pull && pytest tests/test_ec2_ports_rules.py -v -s`

## Parked

**RESTRICTED_INCOMING_TRAFFIC / restricted-common-ports** — four live
misses 2026-08-28. Rule invokes; GetComplianceDetails stays empty.
Skipped in pytest. Do not spend another 15-minute cycle on it.

FSx (not discovered), S3 default encryption.
