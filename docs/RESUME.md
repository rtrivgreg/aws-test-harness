# Resume note — aws-test-harness

Last updated: 2026-08-28 07:02 EDT

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited,
SSL, logging, public-read, public-write, ACL prohibited.

**EBS** — ENCRYPTED_VOLUMES. Snapshot public-restorable partial.

**EFS** — encrypted, backups, access points.

**CloudTrail** — log-file validation (KMS on other machine).

**EC2** — IMDSv2, restricted SSH.

**Backup** — min frequency/retention.

## In flight

**restricted-common-ports** — 07:00 EDT: wait_for_evaluation passed
(invocation time present) but GetComplianceDetails stayed `[]` for 10m
with ComplianceResourceId scope. That scope is now removed.

Also set MaximumExecutionFrequency=One_Hour, param blockedPorts=3389,
and dump rule/status/compliance summary on empty results.

Re-run: `git pull && pytest tests/test_ec2_ports_rules.py -v -s`

If DEBUG lines show ComplianceType INSUFFICIENT_DATA or no resources
in scope, park this identifier and use vpc-sg-port-restriction-check.

## Parked

FSx (not discovered), S3 default encryption.
