# Resume note — aws-test-harness

Last updated: 2026-08-27 15:38 EDT

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited.

**EBS** — `ENCRYPTED_VOLUMES`. Snapshot public-restorable partial only.

**EFS** — encrypted, automatic backups, access points.

**CloudTrail** — log-file validation this host. KMS on the other machine.

**EC2** — IMDSv2 PASSED. Restricted SSH PASSED 15:38 EDT.

## Next

```bash
git pull
pytest tests/test_ec2_ports_rules.py -v -s
```

Then Backup or stop. Defer FSx unless you specifically want it.
