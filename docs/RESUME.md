# Resume note — aws-test-harness

Last updated: 2026-08-28 06:40 EDT

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited,
SSL, logging, public-read, public-write, ACL prohibited.

**EBS** — ENCRYPTED_VOLUMES. Snapshot public-restorable partial.

**EFS** — encrypted, backups, access points.

**CloudTrail** — log-file validation (KMS on other machine).

**EC2** — IMDSv2, restricted SSH.

**Backup** — min frequency/retention.

## In flight

**restricted-common-ports** — last run 06:38 EDT failed after 12m:
`RuntimeError: Evaluation has not completed yet`.
`LastSuccessfulEvaluationTime` stayed empty. Recorder is fine; SG CIs exist.
Likely first eval was sweeping every SG in the account (exclusion recorder).

Fix on main: scope the rule to the test SG
(`PutConfigRule.Scope.ComplianceResourceId`) and treat
`LastSuccessfulInvocationTime` as completion.

Re-run: `git pull && pytest tests/test_ec2_ports_rules.py -v -s`

## Parked

FSx (not discovered), S3 default encryption.
