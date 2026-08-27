# Resume note — aws-test-harness

Last updated: 2026-08-27 16:39 EDT

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited.

**EBS** — `ENCRYPTED_VOLUMES`. Snapshot public-restorable partial only.

**EFS** — encrypted, automatic backups, access points.

**CloudTrail** — log-file validation this host. KMS on the other machine.

**EC2** — IMDSv2, restricted SSH.

**Backup** — min frequency/retention. PASSED 16:17 EDT.

## Parked

**restricted-common-ports** — empty evaluation results.

**FSx OpenZFS copy-tags** — filesystem created (`fs-0cd37985bac7d2362`) but Config
`ResourceNotDiscoveredException` for `AWS::FSx::FileSystem`. Do not keep the FS.

**S3 default encryption** — skip.

## Hygiene

Destroy Terraform (especially FSx). Stop the recorder when idle.
