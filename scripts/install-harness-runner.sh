#!/usr/bin/env bash
# Install GitHub Actions runner on /mnt/scratchpad. Run on ip-10-0-1-190.
# Usage:
#   RUNNER_TOKEN=XXXX ./scripts/install-harness-runner.sh
# Token: repo Settings → Actions → Runners → New self-hosted runner (1 hour).
set -euo pipefail

RUNNER_VERSION="${RUNNER_VERSION:-2.337.0}"
RUNNER_DIR="${RUNNER_DIR:-/mnt/scratchpad/actions-runner}"
WORK_DIR="${WORK_DIR:-/mnt/scratchpad/actions-runner/_work}"
REPO_URL="${REPO_URL:-https://github.com/rtrivgreg/aws-test-harness}"
LABELS="${LABELS:-self-hosted,linux,harness-ec2}"
TARBALL="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
SHA256="${RUNNER_SHA256:-70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613}"

if [[ -z "${RUNNER_TOKEN:-}" ]]; then
  echo "Set RUNNER_TOKEN from GitHub Settings → Actions → Runners → New self-hosted runner" >&2
  exit 1
fi

if [[ ! -d /mnt/scratchpad ]]; then
  echo "/mnt/scratchpad is not mounted" >&2
  exit 1
fi

mkdir -p "${RUNNER_DIR}" "${WORK_DIR}" \
  /mnt/scratchpad/pytest_tmp/.pytest_cache \
  /mnt/scratchpad/terraform/plugin_cache \
  /mnt/scratchpad/gha-tmp
cd "${RUNNER_DIR}"

if [[ ! -x ./config.sh ]]; then
  curl -fsSL -o "${TARBALL}" \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${TARBALL}"
  echo "${SHA256}  ${TARBALL}" | sha256sum -c -
  tar xzf "${TARBALL}"
fi

if [[ ! -f .runner ]]; then
  ./config.sh --unattended \
    --url "${REPO_URL}" \
    --token "${RUNNER_TOKEN}" \
    --name "ip-10-0-1-190" \
    --labels "${LABELS}" \
    --work "${WORK_DIR}" \
    --replace
fi

sudo ./svc.sh install ubuntu || true
sudo ./svc.sh start
sudo ./svc.sh status
echo "Runner home: ${RUNNER_DIR}"
echo "Work dir:    ${WORK_DIR}"
