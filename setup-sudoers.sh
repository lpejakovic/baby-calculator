#!/usr/bin/env bash
# Lets one user restart the baby-calculator service without a password, and nothing else:
#   sudo systemctl restart baby-calculator
#
# Usage: ./setup-sudoers.sh [user]   (default: the user running the script)
#
# The rule is written to a file with a "." in its name first, which sudo ignores, and only
# renamed into place after visudo has checked it, so a mistake can't break sudo.
set -euo pipefail

USER_NAME="${1:-$(id -un)}"
SYSTEMCTL="$(command -v systemctl)"
TARGET=/etc/sudoers.d/baby-calculator
TMP="$TARGET.new"

if ! id "$USER_NAME" >/dev/null 2>&1; then
    echo "No such user: $USER_NAME" >&2
    exit 1
fi

RULE="$USER_NAME ALL=(root) NOPASSWD: $SYSTEMCTL restart baby-calculator"

printf '%s\n' "$RULE" | sudo tee "$TMP" >/dev/null
sudo chmod 440 "$TMP"
if ! sudo visudo -cf "$TMP"; then
    sudo rm -f "$TMP"
    echo "The rule failed the visudo check; nothing was changed." >&2
    exit 1
fi
sudo mv "$TMP" "$TARGET"

echo "Installed $TARGET:"
echo "  $RULE"
echo "Test: sudo -n systemctl restart baby-calculator"
