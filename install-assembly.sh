#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH LC_ALL=C
[[ $(id -u) = 0 && ${1:-} = --isolated-test ]] || {
    echo 'Usage: sudo bash install-assembly.sh --isolated-test'; exit 1;
}
pkg=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dst=/usr/local/lib/dx213-assembly
[[ ! -e "$dst" && ! -L "$dst" ]] || { echo 'Destination exists; refusing overwrite'; exit 1; }
[[ -f /usr/local/lib/dx213-scheduler/scheduler.sh && -x /bin/python3 ]] || {
    echo 'Install the detection package first; /bin/python3 required'; exit 1;
}
[[ $(df -P /usr/local/lib | awk 'END {print $6}') = / ]] || exit 1
cd "$pkg"
sha256sum -c SHA256SUMS >/dev/null
mkdir -m 700 "$dst"
for name in assemble.py task.sh SHA256SUMS; do
    [[ ! -L "assembly/$name" ]] || exit 1
    cp "assembly/$name" "$dst/$name"
done
chown -R root:root "$dst"
chmod 700 "$dst"
chmod 600 "$dst/assemble.py" "$dst/task.sh" "$dst/SHA256SUMS"
(cd "$dst" && sha256sum -c SHA256SUMS >/dev/null)
echo 'Assembly helper installed, NOT configured. Existing task/package unchanged.'
