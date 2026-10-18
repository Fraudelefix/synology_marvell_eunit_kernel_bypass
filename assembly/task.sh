#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH LC_ALL=C
[[ $(id -u) = 0 && ${1:-} = --isolated-test ]] || exit 1
cd /usr/local/lib/dx213-assembly
sha256sum -c SHA256SUMS >/dev/null
[[ -f target.json ]] || { echo 'Enroll the target pool first'; exit 1; }
# Detection retains its original manifest, guard, lock and log.
/bin/bash /usr/local/lib/dx213-scheduler/scheduler.sh --isolated-test
exec >> /var/log/dx213-scheduler.log 2>&1
date -u
echo 'Beginning targeted DSM pool assembly (preview2)'
rc=0
/bin/python3 /usr/local/lib/dx213-assembly/assemble.py assemble --isolated-test || rc=$?
echo "ASSEMBLY_RESULT=$rc"
exit "$rc"
