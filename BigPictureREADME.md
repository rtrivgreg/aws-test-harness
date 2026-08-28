CPs
--------------------------------------------------------------------------------------------------------------
## CURRENT PUSH 8/28/2026 ACT 
1) email aliases: aws-rtrivgreg@yahoo.com
2) harness (cont)
3) make 3 CPs. Test value change via amplify
4) 4) activate consolidations and ids
 
## Conformance Pack Tooling
- **aws-crud-rules-db** / DynamoDB catalog - system of record for rule curation (parameters, metadata and group bindings).
- **aws-config-rules-all** pack generation - (cpg.py, cpgNG.py)
- **aws-compliance-collector**  - forensics
- **aws-test-harness** = validation evidence TT that proves the parameters chosen in a binding actually produce the expected COMPLIANT / NON_COMPLIANT outcomes on a controlled resource.

## DAILY EC2 / MacBook Ramp-up
please resume https://github.com/rtrivgreg/aws-test-harness.git...

source .venv/bin/activate

export CATALOG_TABLE_NAME="y62db-config-rule-catalog"

export CATALOG_GROUP="default"

export AWS_REGION="us-east-1"

export TEST_RUN_ID=$(uuidgen | tr '[:upper:]' '[:lower:]' | cut -c1-8)

cd repost
cd aws-test-harness
git pull

ubuntu@ip-10-0-1-190:~/repost/aws-test-harness$ aws configservice describe-configuration-recorder-status --region us-east-1
