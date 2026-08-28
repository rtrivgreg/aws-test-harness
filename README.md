# AWS Config Rule Test Harness
Framework for systematically validating AWS Config **managed rules** (and later full conformance packs) using a minimal, Terraform-provisioned resource that can be programmatically toggled between COMPLIANT and NON_COMPLIANT states.

## Design Principles

- **Terraform owns the durable test resources** (S3 bucket first). This gives you drift detection, state, and aligns with Terraform Professional certification goals.
- **Python + pytest owns the rule lifecycle and assertions**.
- **Live catalog** – rule definitions and parameters are read from the same DynamoDB catalog that `cpgNG.py` uses.
- **Unique `test-run-id` tag** on every resource and Config rule for safe identification and cleanup.
- **Dry-run mode** supported throughout.
- Heavily commented so the pattern is clear when extending to EBS, EFS, EC2, CloudTrail, Backup, etc.

## High-level flow (per managed rule)

1. Terraform provisions (or re-uses) a minimal shared S3 bucket tagged with the current `test-run-id`.
2. For each rule under test:
   - `PutConfigRule` with the exact parameters from the DynamoDB catalog / group binding.
   - Assert the rule is active.
   - Force the test bucket into a known **NON_COMPLIANT** state.
   - `StartConfigRulesEvaluation` + poll until evaluation completes.
   - `GetComplianceDetailsByConfigRule` → assert `NON_COMPLIANT` for the test resource.
   - Force the bucket into a known **COMPLIANT** state.
   - Re-evaluate → assert `COMPLIANT`.
   - (Optional) Force an out-of-scope condition → assert `NOT_APPLICABLE`.
   - Delete the Config rule.
3. Terraform can destroy the test resources when the run is finished (or leave them for inspection).

## Repository layout

```
aws-test-harness/
├── README.md
├── requirements.txt
├── pyproject.toml
├── config/
│   └── settings.example.yaml          # local overrides / DynamoDB table names
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── versions.tf
│   └── modules/
│       └── s3_test_bucket/            # minimal S3 bucket for Config rule testing
│           ├── main.tf
│           ├── variables.tf
│           └── outputs.tf
├── src/
│   └── harness/
│       ├── __init__.py
│       ├── catalog.py                 # DynamoDB catalog client
│       ├── config_rule.py             # Put/Delete/StartEvaluation helpers
│       ├── compliance.py              # polling + GetComplianceDetails
│       ├── s3_toggle.py               # force COMPLIANT / NON_COMPLIANT on the test bucket
│       ├── tags.py                    # test-run-id helpers
│       └── dry_run.py
└── tests/
    ├── conftest.py                    # pytest fixtures (session-scoped resources, run-id, etc.)
    ├── test_s3_rules.py               # first vertical slice
    └── helpers.py
```

## Prerequisites

- AWS credentials with permissions to:
  - Manage Config rules (`config:PutConfigRule`, `config:DeleteConfigRule`, `config:StartConfigRulesEvaluation`, `config:GetComplianceDetailsByConfigRule`, `config:DescribeConfigRuleEvaluationStatus`, …)
  - Read the DynamoDB catalog table
  - Create/update/delete the test S3 bucket (and related Config recording if needed)
- Terraform >= 1.5
- Python >= 3.11
- `pytest`

## Quick start (after cloning)

```bash
# 1. Python deps
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp config/settings.example.yaml config/settings.yaml
# edit table name, group/binding, region, etc.

# 3. Provision the minimal S3 test resource
cd terraform
terraform init
terraform apply -var="test_run_id=$(uuidgen)"   # or any unique value
cd ..

# 4. Run the S3 rule tests (dry-run first)
pytest tests/test_s3_rules.py -v --dry-run

# 5. Real run
pytest tests/test_s3_rules.py -v
```

## Extending to other families

1. Add a new Terraform module under `terraform/modules/` (ebs_test_volume, efs_test_filesystem, …).
2. Add a corresponding `*_toggle.py` that knows how to drive the resource COMPLIANT ↔ NON_COMPLIANT.
3. Register the new resource type in the catalog interface and in `conftest.py`.
4. Write a new `test_<family>_rules.py` that re-uses the same fixtures and flow.

## Safety notes

- Every resource and Config rule created by this harness **must** carry the `test-run-id` tag.
- Prefer running in a dedicated test account.
- Always start with `--dry-run`.
- The framework never deletes resources that lack the expected `test-run-id` tag.

DAILY EC2 
# ubuntu EC2 (not macbook)
please resume https://github.com/rtrivgreg/aws-test-harness.git

source .venv/bin/activate

export CATALOG_TABLE_NAME="y62db-config-rule-catalog"
export CATALOG_GROUP="default"
export AWS_REGION="us-east-1"
export TEST_RUN_ID=$(uuidgen | tr '[:upper:]' '[:lower:]' | cut -c1-8)

cd repost
ubuntu@ip-10-0-1-190:~/repost$ 
cd aws-test-harness
git pull

ubuntu@ip-10-0-1-190:~/repost/aws-test-harness$ aws configservice describe-configuration-recorder-status \
  --region us-east-1
{
    "ConfigurationRecordersStatus": [
        {
            "arn": "arn:aws:config:us-east-1:418295699841:configuration-recorder/default/eu6cs99surp9xy02",
            "name": "default",
            "lastStartTime": "2026-08-28T09:10:06.063000+00:00",
            "lastStopTime": "2026-08-28T05:01:36.453000+00:00",
            "recording": true,
            "lastStatus": "SUCCESS",
            "lastStatusChangeTime": "2026-08-28T09:10:16.775000+00:00"
        }
    ]
}
