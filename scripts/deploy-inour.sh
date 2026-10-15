#!/usr/bin/env bash
# Disabled by workflow gate until the operator confirms SSH/Linux/symlink support.
# Requires a dedicated pre-created root ending in /isegye-idol with an ownership marker.
set -euo pipefail
for name in INOUR_SSH_HOST INOUR_SSH_USER INOUR_SSH_PRIVATE_KEY INOUR_SSH_KNOWN_HOSTS INOUR_DEPLOY_ROOT GITHUB_SHA; do
  [[ -n "${!name:-}" ]] || { echo "Missing configuration: $name" >&2; exit 1; }
done
[[ "${GITHUB_REF:-}" == 'refs/heads/main' ]] || { echo 'Production deploy is restricted to main.' >&2; exit 1; }
port="${INOUR_SSH_PORT:-22}"
[[ "$port" =~ ^[0-9]+$ && "$port" -ge 1 && "$port" -le 65535 ]] || exit 1
[[ "$INOUR_SSH_HOST" =~ ^[a-zA-Z0-9.-]+$ ]] || exit 1
[[ "$INOUR_SSH_USER" =~ ^[a-zA-Z_][a-zA-Z0-9_-]*$ ]] || exit 1
[[ "$GITHUB_SHA" =~ ^[a-f0-9]{40}$ ]] || exit 1
[[ "$INOUR_DEPLOY_ROOT" =~ ^/[a-zA-Z0-9_./-]+/isegye-idol$ && "$INOUR_DEPLOY_ROOT" != *'..'* ]] || { echo 'Use a dedicated absolute root ending in /isegye-idol.' >&2; exit 1; }
[[ -f dist/index.html && -f dist/build-info.json ]] || { echo 'Missing tested build.' >&2; exit 1; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
chmod 700 "$tmp"
printf '%s\n' "$INOUR_SSH_PRIVATE_KEY" > "$tmp/key"
printf '%s\n' "$INOUR_SSH_KNOWN_HOSTS" > "$tmp/known_hosts"
chmod 600 "$tmp/key" "$tmp/known_hosts"
ssh_opts=(-i "$tmp/key" -o BatchMode=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$tmp/known_hosts" -o ConnectTimeout=15)
target="$INOUR_SSH_USER@$INOUR_SSH_HOST"
release="$GITHUB_SHA-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
[[ "$release" =~ ^[a-zA-Z0-9-]+$ ]] || exit 1
ssh "${ssh_opts[@]}" -p "$port" "$target" "bash -s -- '$INOUR_DEPLOY_ROOT' '$release'" <<'REMOTE'
set -euo pipefail
root="$1"; release="$2"
[[ -d "$root" && -f "$root/.isegye-fansite-root" ]] || { echo 'Dedicated site ownership marker is missing.' >&2; exit 1; }
[[ ! -e "$root/current" || -L "$root/current" ]] || { echo 'Refusing to replace a non-symlink current path.' >&2; exit 1; }
mkdir -p "$root/releases"
mkdir "$root/releases/$release"
REMOTE
tar -czf "$tmp/site.tar.gz" -C dist .
scp "${ssh_opts[@]}" -P "$port" "$tmp/site.tar.gz" "$target:$INOUR_DEPLOY_ROOT/releases/$release/site.tar.gz"
ssh "${ssh_opts[@]}" -p "$port" "$target" "bash -s -- '$INOUR_DEPLOY_ROOT' '$release'" <<'REMOTE'
set -euo pipefail
root="$1"; release="$2"; dir="$root/releases/$release"
[[ -f "$root/.isegye-fansite-root" && -f "$dir/site.tar.gz" ]] || exit 1
tar -xzf "$dir/site.tar.gz" -C "$dir"
rm "$dir/site.tar.gz"
[[ -f "$dir/index.html" && -f "$dir/build-info.json" ]] || exit 1
if [[ -L "$root/current" ]]; then readlink "$root/current" > "$root/previous-release.txt"; fi
ln -s "releases/$release" "$root/.current-$release"
mv -Tf "$root/.current-$release" "$root/current"
echo 'Dedicated site release switched. Existing unrelated sites were not modified.'
REMOTE
