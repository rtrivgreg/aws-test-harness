#!/usr/bin/env bash
# Put RESTRICTED_INCOMING_TRAFFIC, start one eval, dump every Config view.
# Does not wait 10 minutes and does not delete the rule.
set -euo pipefail
REGION="${AWS_REGION:-us-east-1}"
RULE="${1:-harness-forensic-restricted-common-ports}"
SG="${2:-}"

if [[ -z "$SG" ]]; then
  echo "Usage: $0 [rule-name] <security-group-id>"
  echo "Example: $0 harness-forensic-rcp sg-07fa913d0e8961833"
  exit 1
fi

cat > /tmp/forensic-rcp.json <<EOF
{
  "ConfigRuleName": "$RULE",
  "Description": "Forensic probe for RESTRICTED_INCOMING_TRAFFIC",
  "Source": {
    "Owner": "AWS",
    "SourceIdentifier": "RESTRICTED_INCOMING_TRAFFIC"
  },
  "InputParameters": "{\"blockedPorts\": \"3389\"}",
  "MaximumExecutionFrequency": "One_Hour",
  "Scope": {
    "ComplianceResourceTypes": ["AWS::EC2::SecurityGroup"]
  }
}
EOF

echo "=== put-config-rule $RULE ==="
aws configservice put-config-rule --region "$REGION" --config-rule file:///tmp/forensic-rcp.json

echo "=== start-config-rules-evaluation ==="
aws configservice start-config-rules-evaluation --region "$REGION" --config-rule-names "$RULE" || true

echo "=== sleep 30s ==="
sleep 30

echo "=== describe-config-rules ==="
aws configservice describe-config-rules --region "$REGION" --config-rule-names "$RULE"

echo "=== describe-config-rule-evaluation-status ==="
aws configservice describe-config-rule-evaluation-status --region "$REGION" --config-rule-names "$RULE"

echo "=== describe-compliance-by-config-rule ==="
aws configservice describe-compliance-by-config-rule --region "$REGION" --config-rule-names "$RULE"

echo "=== get-compliance-details-by-config-rule ==="
aws configservice get-compliance-details-by-config-rule --region "$REGION" --config-rule-name "$RULE"

echo "=== get-compliance-details-by-resource $SG ==="
aws configservice get-compliance-details-by-resource --region "$REGION" \
  --resource-type AWS::EC2::SecurityGroup --resource-id "$SG" || true

echo "=== get-resource-config-history $SG (limit 1) ==="
aws configservice get-resource-config-history --region "$REGION" \
  --resource-type AWS::EC2::SecurityGroup --resource-id "$SG" --limit 1 \
  --query "configurationItems[0].{t:configurationItemCaptureTime,st:configurationItemStatus,rid:resourceId}"

echo
echo "Rule left in place: $RULE"
echo "Delete later: aws configservice delete-config-rule --config-rule-name $RULE --region $REGION"
