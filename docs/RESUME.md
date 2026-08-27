# Resume note — aws-test-harness

Last updated: 2026-08-27 (afternoon, after missing Grok transcript)

Source of truth: git on `main`, not the chat history.

## Locked live proofs (ran against Config and documented)

**S3 full cycle**
- `S3_BUCKET_VERSIONING_ENABLED`
- `S3_LIFECYCLE_POLICY_CHECK`
- `S3_VERSION_LIFECYCLE_POLICY_CHECK`
- `S3_BUCKET_LEVEL_PUBLIC_ACCESS_PROHIBITED`

**EBS**
- `ENCRYPTED_VOLUMES` — two attached volumes. Proven.
- `EBS_SNAPSHOT_PUBLIC_RESTORABLE_CHECK` — **partial.** Periodic + account-scoped.
  NON_COMPLIANT proven when harness snapshot is public. COMPLIANT not isolatable
  if any other snapshot in the account is public. Do not keep re-running in a shared account.

**S3 skip:** `S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED` — default AES256; cannot prove NON_COMPLIANT by delete_bucket_encryption.

## Implemented on main Aug 27 (code + Terraform + pytest; live proof not restated here)

Work that landed today after the S3/EBS lock. Treat as **ready to run**, not automatically “locked” unless you already saw PASSED in the other thread.

| Family | Tests | Notes |
|--------|--------|--------|
| S3 extra | `test_s3_ssl_rules.py`, `test_s3_logging_rules.py` | SSL-requests-only; access-logging target bucket |
| EFS | `test_efs_rules.py`, `test_efs_backup_rules.py`, `test_efs_access_point_rules.py` | Two FS + APs + backup toggle |
| CloudTrail | `test_cloudtrail_rules.py`, `test_cloudtrail_encryption_rules.py` | Validation toggle; KMS ARN |
| FSx | `test_fsx_rules.py` | OpenZFS SINGLE_AZ_1; copy-tags-to-backups |
| EC2 | `test_ec2_rules.py`, `test_ec2_ssh_rules.py`, `test_ec2_ports_rules.py` | IMDSv2; incoming SSH; restricted-common-ports / RDP 3389 |
| Backup | `test_backup_rules.py` | Min frequency / retention |

Last code commits today: ports test (skip eval-status gate; tag-nudge SG; full blocked-port params), then README setup text.

## Suggested next run

If you are not sure what already PASSED live today, re-prove the last slice:

```bash
git pull
source .venv/bin/activate
export CATALOG_TABLE_NAME="y62db-config-rule-catalog"
export CATALOG_GROUP="default"
export AWS_REGION="us-east-1"
export TEST_RUN_ID=$(uuidgen | tr '[:upper:]' '[:lower:]' | cut -c1-8)
aws configservice start-configuration-recorder \
  --configuration-recorder-name default --region "$AWS_REGION"
pytest tests/test_ec2_ports_rules.py -v -s
```

Need `TF_VAR_ec2_subnet_id` (or the module’s default subnet lookup) for EC2/FSx/EBS attach paths.

If ports already passed, next cheapest proof is `tests/test_efs_rules.py` (`EFS_ENCRYPTED_CHECK`) — same two-resource pattern as EBS encryption.

## Hygiene

- Destroy Terraform after the session (`cd terraform && terraform destroy -auto-approve`).
- Delete leftover `harness-*` Config rules.
- Stop the customer managed recorder when idle (no AWS penalty). Start it before the next run.
- Local Terraform state per machine is fine; use a fresh `TEST_RUN_ID` on EC2 vs Mac.
