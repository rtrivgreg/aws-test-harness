#!/usr/bin/env bash
# Refuse any plan that destroys. Usage:
#   ./scripts/tf-safe.sh plan
#   ./scripts/tf-safe.sh apply    # requires HARNESS_ALLOW_TF_APPLY=1
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TF="$ROOT/terraform"
cd "$TF"
cmd=${1:-plan}
terraform init -input=false >/dev/null
terraform plan -input=false -out=tfplan
python3 - <<'PY'
import json, subprocess, sys
raw = subprocess.check_output(["terraform", "show", "-json", "tfplan"])
plan = json.loads(raw)
dest = []
for c in plan.get("resource_changes", []):
    acts = c.get("change", {}).get("actions", [])
    if "delete" in acts:
        dest.append(c.get("address"))
if dest:
    print("REFUSING PLAN: destroys")
    for a in dest:
        print("  ", a)
    sys.exit(2)
print("Plan has 0 destroys")
PY
if [[ "$cmd" == "apply" ]]; then
  if [[ "${HARNESS_ALLOW_TF_APPLY:-}" != "1" ]]; then
    echo "Refusing apply. Set HARNESS_ALLOW_TF_APPLY=1 after reading the plan."
    exit 3
  fi
  terraform apply -input=false tfplan
  terraform state pull > "$ROOT/../tfstate-$(date +%Y%m%d-%H%M%S).json" || true
fi
