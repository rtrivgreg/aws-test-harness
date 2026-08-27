# Resume note — aws-test-harness

Last updated: 2026-08-27 15:31 EDT

## Locked live proofs

**S3** — versioning, lifecycle, version-lifecycle, public-access prohibited.

**EBS** — `ENCRYPTED_VOLUMES`. Snapshot public-restorable partial only.

**EFS** — encrypted, automatic backups, access points.

**CloudTrail** — log-file validation this host. KMS encryption done on the other machine.

**EC2** — IMDSv2 (`test_ec2_rules.py`) PASSED 15:31 EDT.

## Next

```bash
git pull
pytest tests/test_ec2_ssh_rules.py -v -s
```

Then `tests/test_ec2_ports_rules.py`. Defer FSx.
