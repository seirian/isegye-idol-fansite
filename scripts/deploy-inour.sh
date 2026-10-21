#!/usr/bin/env bash
# Retired generic SSH/rsync entry point; all writes use the fixed-root SFTP guard.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/inour_sftp.py
