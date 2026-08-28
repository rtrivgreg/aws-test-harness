# Resume note — aws-test-harness

Last updated: 2026-08-28 06:20 EDT

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited,
SSL, logging, public-read, public-write, ACL prohibited
(`cfg-test-ef57dcf4-ca589695`).

**EBS** — ENCRYPTED_VOLUMES. Snapshot public-restorable partial.

**EFS** — encrypted, backups, access points.

**CloudTrail** — log-file validation (KMS on other machine).

**EC2** — IMDSv2, restricted SSH.

**Backup** — min frequency/retention.

## In flight

**restricted-common-ports / RESTRICTED_INCOMING_TRAFFIC** — FAILED 05:45 EDT.
Config recorded SG `sg-07fa913d0e8961833` (CI OK) but rule published
zero EvaluationResults (`Last results: []`). Recorder is
EXCLUSION_BY_RESOURCE_TYPES (IAM only excluded), so discovery is fine.

Fix on main: same eval path as locked SSH test — CI wait, then
`start_evaluation` + `wait_for_evaluation`, then assert with
`after_timestamp`. Do not swallow StartConfigRulesEvaluation errors.

Re-run: `git pull && pytest tests/test_ec2_ports_rules.py -v -s`

## Parked

FSx (not discovered), S3 default encryption.
