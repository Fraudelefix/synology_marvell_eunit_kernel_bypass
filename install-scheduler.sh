#!/bin/bash
# GPL-2.0-only. Copies a separate package; never creates/runs a DSM task.
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH LC_ALL=C
[[ $(id -u) = 0 ]] || { echo 'Root required'; exit 1; }
[[ ${1:-} = stage && ${2:-} = --isolated-test ]] || {
    echo 'Usage: install-scheduler.sh stage --isolated-test'; exit 2;
}
pkg=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dst=/usr/local/lib/dx213-scheduler
[[ ! -e "$dst" && ! -L "$dst" ]] || { echo 'Destination exists: refusing overwrite'; exit 1; }
[[ $(cat /proc/sys/kernel/syno_hw_version) = DS920+ ]] || exit 1
[[ $(uname -r) = 4.4.302+ ]] || exit 1
[[ $(uname -v) = '#90080 SMP Wed Jul 22 00:08:29 CST 2026' ]] || exit 1
[[ $(df -P /usr/local/lib | awk 'END {print $6}') = / ]] || {
    echo 'Destination must be on the root filesystem'; exit 1;
}
cd "$pkg"
sha256sum -c SHA256SUMS >/dev/null
# Copy only reviewed manifest entries; exclude runtime proofs/activation files.
mkdir -m 700 "$dst"
while read -r digest rel; do
    [[ "$rel" != /* && "$rel" != *..* && ! -L "$rel" && -f "$rel" ]] || exit 1
    mkdir -p "$dst/$(dirname -- "$rel")"
    cp -- "$rel" "$dst/$rel"
done < SHA256SUMS
cp SHA256SUMS "$dst/SHA256SUMS"
chown -R root:root "$dst"
chmod -R go-w "$dst"
(cd "$dst" && sha256sum -c SHA256SUMS >/dev/null)
echo 'Staged only. No task/service was created, disabled or started.'
echo 'Read SCHEDULER.md before switching from the pre-storage service.'
