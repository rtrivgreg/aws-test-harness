# Resume note — aws-test-harness

Last updated: 2026-08-26

## Where we left off

**S3 vertical slice is locked.** Full compliance cycles proven for:

- `S3_BUCKET_VERSIONING_ENABLED`
- `S3_LIFECYCLE_POLICY_CHECK`
- `S3_VERSION_LIFECYCLE_POLICY_CHECK`
- `S3_BUCKET_LEVEL_PUBLIC_ACCESS_PROHIBITED`

**Intentionally out of default allowlist:**

- `S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED` — modern S3 default encryption means
  `delete_bucket_encryption` does not yield a Config CI with encryption absent;
  NON_COMPLIANT leg cannot be proven the simple way.

**Next workstream (not started):** EBS family as second vertical slice
(Terraform volume + 1–2 managed rules + same CI/eval/assert engine).

Do **not** set `ALLOW_ALL_S3_RULES=1` until more strategies exist.

## Config recorder and cost

You **can stop the customer managed configuration recorder** with no AWS penalty
or termination fee. Billing is usage-based:

| While recording | You pay for new configuration items (CIs) + rule evaluations you trigger |
|-----------------|--------------------------------------------------------------------------|
| While stopped   | No new CIs from that recorder → that CI charge stops                     |

Notes:

- Previously recorded history remains available.
- Active Config **rules** can still incur **evaluation** charges if something
  triggers them; for a quiet overnight, stopping the recorder is the main lever
  for CI cost. Delete leftover harness rules if any remain.
- Service-linked recorders (if any) cannot be stopped the same way; this note
  is about the **customer managed** recorder (`default` in this account).
- On resume, **start the recorder again** before running the harness or
  discovery waits will fail.

```bash
# Stop (overnight / idle)
aws configservice stop-configuration-recorder --configuration-recorder-name default --region us-east-1

# Start (before tests)
aws configservice start-configuration-recorder --configuration-recorder-name default --region us-east-1

# Confirm
aws configservice describe-configuration-recorder-status --region us-east-1
```

## State: Mac vs EC2

Local Terraform state on each machine is **OK**. Resources are ephemeral and
tagged (`Project=aws-config-test-harness`). No remote state required until CI
needs a shared backend.

- Prefer one host per active test session.
- Destroy on the host that applied, or clean up by tag.
- Use a fresh `TEST_RUN_ID` on EC2 to avoid name collisions with Mac leftovers.

## EC2 resume checklist

```bash
cd ~/repos/aws-test-harness   # or your clone path
git pull

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export CATALOG_TABLE_NAME="y62db-config-rule-catalog"
export CATALOG_GROUP="default"
export AWS_REGION="us-east-1"
export TEST_RUN_ID=$(uuidgen | tr '[:upper:]' '[:lower:]' | cut -c1-8)

# Config must be recording
aws configservice start-configuration-recorder \
  --configuration-recorder-name default \
  --region "$AWS_REGION"

cd terraform
terraform init
cd ..

pytest tests/test_s3_rules.py -v -s
```

Optional end of session:

```bash
cd terraform && terraform destroy -auto-approve
aws configservice stop-configuration-recorder \
  --configuration-recorder-name default \
  --region us-east-1
```

## Engine reminders (already fixed in code)

- Lowercase test-run-id / bucket names
- Sanitized Config rule names
- Wait for Config discovery, then for CI attribute state (not only newer timestamp)
- Start evaluation clock only after CI is ready
- Assert only results newer than eval_ts with expected compliance type
- Rate-limit retries on StartConfigRulesEvaluation
- Best-effort rule delete; pytest timeout 1800s
