#!/usr/bin/env bash
# Deploys origin/main to the live folder, but only a commit that passed CI.
#
#   deploy/deploy.sh            deploy the latest origin/main
#   deploy/deploy.sh --check    only show what would happen
#
# Works from any copy of the repository; it always acts on LIVE_DIR. Steps: refuse if the live folder has local
# edits, fast-forward to origin/main, install requirements if they changed, restart the service and wait until
# /health reports the new version. If that doesn't happen, it rolls back to the previous commit and restarts again.
set -euo pipefail

LIVE_DIR=${LIVE_DIR:-/var/www/bc.luka-pejakovic.from.hr/baby-calculator}
SITE=${SITE:-https://bc.luka-pejakovic.from.hr}
SERVICE=baby-calculator
PIP=${PIP:-bc-env/bin/pip}
HEALTH_TRIES=${HEALTH_TRIES:-30}   # seconds to wait for /health after the restart
HEALTH_DELAY=${HEALTH_DELAY:-1}
CHECK_ONLY=false
[ "${1:-}" = "--check" ] && CHECK_ONLY=true

cd "$LIVE_DIR"
fail() { echo "deploy: $*" >&2; exit 1; }

# The live folder only changes through this script
if ! git diff --quiet || ! git diff --cached --quiet; then
    fail "the live folder has uncommitted changes; refusing to deploy"
fi

git fetch --quiet origin main
current=$(git rev-parse HEAD)
target=$(git rev-parse origin/main)
if [ "$current" = "$target" ]; then
    echo "deploy: already at ${target:0:7}, nothing to do"
    exit 0
fi
git merge-base --is-ancestor "$current" "$target" || fail "live HEAD ${current:0:7} is not part of origin/main; refusing"

# CI (lint, unit, browser and accessibility tests) must have passed for exactly this commit
ci=$(gh run list --workflow tests.yml --commit "$target" --json status,conclusion -q '.[0] | "\(.status) \(.conclusion)"')
[ "$ci" = "completed success" ] || fail "CI for ${target:0:7} is '${ci:-not started}'; deploy after it passes"

echo "deploy: ${current:0:7} -> ${target:0:7}"
git log --oneline "$current..$target"
$CHECK_ONLY && { echo "deploy: --check, nothing changed"; exit 0; }

requirements_changed=false
git diff --quiet "$current" "$target" -- requirements.txt || requirements_changed=true

install_requirements() { "$PIP" install --quiet -r requirements.txt; }
version() { sed -n 's/^APP_VERSION = "\(.*\)"$/\1/p' app.py; }
healthy() {
    local expected
    expected=$(version)
    for _ in $(seq "$HEALTH_TRIES"); do
        if curl -fsS --max-time 5 "$SITE/health" 2>/dev/null | grep -q "\"version\":\"$expected\""; then
            return 0
        fi
        sleep "$HEALTH_DELAY"
    done
    return 1
}

git merge --ff-only --quiet "$target"
$requirements_changed && install_requirements
sudo -n systemctl restart "$SERVICE"

if healthy; then
    echo "deploy: live at ${target:0:7}, version $(version)"
    exit 0
fi

echo "deploy: /health did not report version $(version); rolling back to ${current:0:7}" >&2
git reset --hard --quiet "$current"
$requirements_changed && install_requirements
sudo -n systemctl restart "$SERVICE"
healthy && echo "deploy: rolled back, live at ${current:0:7}" >&2
exit 1
